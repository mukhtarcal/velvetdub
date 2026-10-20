"""Dubbing: the rules (sentences, room, samples, fitting), the voice service connection, the
pipeline end to end on fakes, and the API. No network, keys, Demucs or ffmpeg needed."""

import wave
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from tests.conftest import FakeMediaTool
from tests.test_api import CLIENT, wait_until_finished
from tests.test_pipeline import RecordingObserver
from velvetdub.api.app import create_app
from velvetdub.container import Container
from velvetdub.domain.dubbing import LINE_SAMPLE_RATE, Placement, SynthesisRequest
from velvetdub.domain.manifest import TrackKind
from velvetdub.domain.transcript import Segment, Transcript, Word
from velvetdub.errors import ProviderError, QuotaExceededError, StageFailedError
from velvetdub.features.dubbing.cast import clone_cast
from velvetdub.features.dubbing.samples import plan_cast
from velvetdub.features.dubbing.sentences import merge_sentences
from velvetdub.features.dubbing.speech import LineRecorder
from velvetdub.features.dubbing.timing import slots
from velvetdub.features.translation.translator import Translator
from velvetdub.media.dialogue import (
    assemble_dialogue,
    placed_starts,
    trim_silence,
    wav_seconds,
)
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.providers.base import TextGenerator
from velvetdub.providers.cartesia import CartesiaSynthesizer
from velvetdub.providers.fake import FakeSynthesizer, FakeTranscriber, write_silence, write_tone

# --- the rules -------------------------------------------------------------------------------


def seg(id_: str, start: float, end: float, text: str, speaker: str | None = "A") -> Segment:
    return Segment(id=id_, start=start, end=end, text=text, speaker=speaker)


def test_an_unfinished_line_joins_the_next_one_when_the_gap_is_brief() -> None:
    transcript = Transcript(
        language="en",
        segments=[
            seg("s0", 97.2, 98.3, "we are"),
            seg("s1", 98.9, 102.8, "going to need a miracle."),
        ],
    )
    merged = merge_sentences(transcript).segments
    assert len(merged) == 1
    assert merged[0].id == "d0"
    assert (merged[0].start, merged[0].end) == (97.2, 102.8)
    assert merged[0].text == "we are going to need a miracle."


def test_a_pause_in_the_film_is_kept_even_in_the_middle_of_a_sentence() -> None:
    transcript = Transcript(
        language="en",
        segments=[
            seg("s0", 97.2, 98.3, "we are"),  # then 2.5 s of silence, as the actor held it
            seg("s1", 100.8, 102.8, "going to need a miracle."),
        ],
    )
    merged = merge_sentences(transcript).segments
    assert [(s.start, s.text) for s in merged] == [
        (97.2, "we are"),
        (100.8, "going to need a miracle."),
    ]


def words(*items: tuple[str, float, float]) -> tuple[Word, ...]:
    return tuple(Word(text=text, start=start, end=end) for text, start, end in items)


def spoken(id_: str, *items: tuple[str, float, float], speaker: str = "A") -> Segment:
    parts = words(*items)
    return Segment(
        id=id_,
        start=parts[0].start,
        end=parts[-1].end,
        text=" ".join(w.text for w in parts),
        speaker=speaker,
        words=parts,
    )


# The real line: "what doesn't kill me [4 seconds of silence] just makes me stronger." The service
# wrote the silence down as the length of the word "me".
ULTRON = spoken(
    "s13",
    ("But—", 44.24, 44.53),
    ("Like", 44.79, 45.02),
    ("the", 45.05, 45.18),
    ("men", 45.18, 45.42),
    ("said,", 45.55, 45.98),
    ("what", 46.40, 46.47),
    ("doesn't", 46.56, 46.89),
    ("kill", 46.89, 47.24),
    ("me", 47.37, 51.81),
    ("just", 52.07, 52.55),
    ("makes", 52.72, 52.93),
    ("me", 53.05, 53.15),
    ("stronger.", 53.15, 53.87),
)


def test_a_pause_hidden_inside_a_stretched_word_splits_the_line_there() -> None:
    merged = merge_sentences(Transcript(language="en", segments=[ULTRON])).segments
    assert [s.id for s in merged] == ["d0", "d1"]
    assert merged[0].text == "But— Like the men said, what doesn't kill me"
    assert merged[1].text == "just makes me stronger."
    assert merged[1].start == 52.07  # said after the pause, not straight after "me"
    assert merged[0].end == pytest.approx(47.87)  # where "me" really stops, not 51.81
    assert merged[1].start - merged[0].end > 4.0


def test_a_gap_between_words_splits_a_line_too() -> None:
    line = spoken("s0", ("Wait.", 1.0, 1.5), ("Now", 3.0, 3.3), ("go", 3.4, 3.6))
    merged = merge_sentences(Transcript(language="en", segments=[line])).segments
    assert [(s.start, s.text) for s in merged] == [(1.0, "Wait."), (3.0, "Now go")]


def test_a_line_with_no_pause_in_it_is_left_exactly_as_it_was() -> None:
    line = spoken("s0", ("Hello", 1.0, 1.4), ("there,", 1.5, 1.9), ("friend.", 2.0, 2.6))
    merged = merge_sentences(Transcript(language="en", segments=[line])).segments
    assert len(merged) == 1
    assert (merged[0].start, merged[0].end, merged[0].text) == (1.0, 2.6, "Hello there, friend.")


def test_a_word_stretched_at_the_end_of_a_line_does_not_hide_the_pause_after_it() -> None:
    first = spoken("s0", ("so", 0.0, 0.3), ("what", 0.4, 3.9))  # "what" really lasts about 0.7 s
    second = spoken("s1", ("now", 4.5, 4.9))
    merged = merge_sentences(Transcript(language="en", segments=[first, second])).segments
    assert [s.text for s in merged] == ["so what", "now"]  # 3.4 s of silence, not 0.6 s


def test_finished_sentences_other_speakers_and_long_gaps_are_kept_apart() -> None:
    transcript = Transcript(
        language="en",
        segments=[
            seg("s0", 0, 1, "Hello there."),  # finished
            seg("s1", 1.2, 2, "I think"),
            seg("s2", 2.2, 3, "so too", speaker="B"),  # someone else
            seg("s3", 8, 9, "later on,"),  # unfinished, but 5 s of silence is a new scene
            seg("s4", 9.5, 10, "still talking"),
        ],
    )
    texts = [s.text for s in merge_sentences(transcript).segments]
    assert texts == ["Hello there.", "I think", "so too", "later on, still talking"]


def test_a_joined_line_never_runs_longer_than_fifteen_seconds() -> None:
    transcript = Transcript(
        language="en",
        segments=[seg(f"s{i}", i * 4.0, i * 4.0 + 3.5, f"part {i},") for i in range(6)],
    )
    for merged in merge_sentences(transcript).segments:
        assert merged.duration <= 15.0


def test_a_line_may_run_a_little_into_the_pause_after_it_but_never_into_the_next_line() -> None:
    segments = [seg("a", 0, 2, "x"), seg("b", 3.0, 4, "y"), seg("c", 10, 11, "z")]
    assert slots(segments, film_seconds=60) == pytest.approx([2.9, 2.0, 2.0])


def test_every_line_gets_at_least_a_short_slot() -> None:
    assert slots([seg("a", 0, 0.1, "x"), seg("b", 0.2, 1, "y")], 60)[0] == 0.3


def test_each_speaker_gets_a_clear_sample_and_a_barely_heard_one_borrows() -> None:
    transcript = Transcript(
        language="en",
        segments=[
            *(seg(f"a{i}", i * 5.0, i * 5.0 + 4.0, "long line") for i in range(6)),
            seg("b0", 40, 40.5, "Hey", speaker="B"),
            seg("c0", 50, 53, "A real line", speaker="C"),
            seg("c1", 55, 58, "Another one", speaker="C"),
        ],
    )
    plan = plan_cast(transcript)
    assert sum(end - start for start, end in plan.spans["A"]) <= 16.0  # about 15 s is plenty
    assert plan.spans["A"] == sorted(plan.spans["A"])
    assert plan.borrows == {"B": "A"}
    assert "C" not in plan.borrows


def test_a_film_with_no_clear_speech_cannot_have_a_voice_copied(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    transcript = Transcript(language="en", segments=[seg("a", 0, 0.4, "Hi")])
    with pytest.raises(ProviderError, match="no clear speech"):
        clone_cast(
            transcript,
            dialogue=tmp_path / "dialogue.wav",
            sample_path=lambda speaker: tmp_path / f"{speaker}.wav",
            name_for=lambda speaker: speaker,
            synthesizer=FakeSynthesizer(),
            media=media,
        )


def test_cloning_cuts_each_sample_from_the_dialogue_and_names_the_voice(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    transcript = Transcript(
        language="en",
        segments=[seg("a", 0, 5, "line one"), seg("b", 10, 15, "line two", speaker="B")],
    )
    synthesizer = FakeSynthesizer()
    voices = clone_cast(
        transcript,
        dialogue=tmp_path / "dialogue.wav",
        sample_path=lambda speaker: tmp_path / f"{speaker}.wav",
        name_for=lambda speaker: f"film-{speaker}",
        synthesizer=synthesizer,
        media=media,
    )
    assert voices.voices == {"A": "clone-film-A", "B": "clone-film-B"}
    assert voices.provider == "fake:default"
    assert media.cut_calls == [[(0, 5)], [(10, 15)]]


# --- fitting a line --------------------------------------------------------------------------


def recorder(media: FakeMediaTool) -> tuple[LineRecorder, FakeSynthesizer]:
    synthesizer = FakeSynthesizer()
    return LineRecorder(synthesizer, media), synthesizer


def test_a_line_that_fits_is_recorded_once_at_the_natural_pace(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, synthesizer = recorder(media)
    recorded = lines.record("x" * 20, "v", "es", 3.0, tmp_path / "l.wav")  # 1.0 s
    assert recorded is not None
    assert recorded.takes == 1
    assert recorded.seconds == pytest.approx(1.0, abs=0.01)
    assert [r.speed for r in synthesizer.spoken] == [1.0]
    assert media.tempo_calls == []


def test_a_long_line_is_asked_for_faster_before_anything_is_squeezed(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, synthesizer = recorder(media)
    recorded = lines.record("x" * 100, "v", "es", 4.0, tmp_path / "l.wav")  # 5.0 s at 1.0
    assert recorded is not None
    assert [r.speed for r in synthesizer.spoken] == [1.0, pytest.approx(5.0 / 4.0 * 1.02)]
    assert recorded.seconds <= 4.0 + 0.1
    assert recorded.takes == 2
    assert media.tempo_calls == []


def test_the_last_resort_squeezes_the_recording_by_a_little(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, synthesizer = recorder(media)
    recorded = lines.record("x" * 100, "v", "es", 3.0, tmp_path / "l.wav")
    assert recorded is not None
    assert synthesizer.spoken[-1].speed == 1.5  # as fast as the service goes
    assert len(media.tempo_calls) == 1 and 1.0 < media.tempo_calls[0] <= 1.2
    assert recorded.seconds == pytest.approx(3.0, abs=0.1)
    assert recorded.takes == 2  # a little long is squeezed, not asked for again and again


def test_a_line_that_cannot_be_made_to_fit_is_kept_not_cut(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, _ = recorder(media)
    recorded = lines.record("x" * 200, "v", "es", 2.0, tmp_path / "l.wav")
    assert recorded is not None
    assert recorded.seconds > 2.0  # the dub pushes the next line back instead
    assert recorded.takes == 4  # it was tried the most times allowed


def test_the_silence_a_voice_puts_round_a_line_is_cut_off_so_it_starts_on_its_word(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, synthesizer = recorder(media)
    synthesizer.padding = 0.3  # 0.3 s of quiet before and after, as real voices do
    dest = tmp_path / "l.wav"
    recorded = lines.record("x" * 20, "v", "es", 3.0, dest)  # a 1.0 s word
    assert recorded is not None
    assert recorded.seconds == pytest.approx(1.0 + 2 * 0.04, abs=0.02)  # not 1.6
    assert wav_seconds(dest) == pytest.approx(recorded.seconds, abs=0.001)


def test_a_one_word_line_the_voice_stretches_is_asked_for_again(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    # "Yo." in a 0.5 s slot: the voice drags it out to 5 s, then 4 s, then gets it right.
    lines, synthesizer = recorder(media)
    synthesizer.plan = [5.0, 4.0, 0.4]
    dest = tmp_path / "l.wav"
    recorded = lines.record("Yo.", "v", "es", 0.5, dest)
    assert recorded is not None
    assert recorded.takes == 3
    assert recorded.seconds == pytest.approx(0.4, abs=0.1)
    assert media.tempo_calls == []  # it fit, so nothing was squeezed
    assert sorted(p.name for p in tmp_path.iterdir()) == ["l.wav"]  # no spare takes left behind


def test_a_take_that_comes_back_silent_is_asked_for_again(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, synthesizer = recorder(media)
    synthesizer.plan = [0, 0.4]
    recorded = lines.record("Yo.", "v", "es", 0.5, tmp_path / "l.wav")
    assert recorded is not None and recorded.takes == 2


def test_when_the_voice_never_makes_a_sound_there_is_no_line(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, synthesizer = recorder(media)
    synthesizer.plan = [0, 0, 0, 0]
    assert lines.record("Yo.", "v", "es", 0.5, tmp_path / "l.wav") is None
    assert list(tmp_path.iterdir()) == []


def test_of_several_bad_takes_the_one_closest_to_its_room_is_kept(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, synthesizer = recorder(media)
    synthesizer.plan = [6.0, 3.0, 8.0, 2.5]
    recorded = lines.record("Yo.", "v", "es", 0.5, tmp_path / "l.wav")
    assert recorded is not None and recorded.takes == 4
    assert recorded.seconds < 2.2  # the 2.5 s take, squeezed a little; not the 6 or 8 s ones


# --- trimming the quiet off a line -----------------------------------------------------------


def test_trimming_cuts_the_quiet_from_both_ends_and_keeps_a_little(tmp_path: Path) -> None:
    line = tmp_path / "l.wav"
    write_tone(line, 1.0, padding=0.5)
    seconds, heard = trim_silence(line)
    assert heard is True
    assert seconds == pytest.approx(1.0 + 2 * 0.04, abs=0.02)
    assert wav_seconds(line) == pytest.approx(seconds, abs=0.001)


def test_trimming_twice_changes_nothing(tmp_path: Path) -> None:
    line = tmp_path / "l.wav"
    write_tone(line, 1.0, padding=0.5)
    first, _ = trim_silence(line)
    before = line.read_bytes()
    second, _ = trim_silence(line)
    assert second == first and line.read_bytes() == before


def test_a_line_with_no_sound_is_reported_and_left_alone(tmp_path: Path) -> None:
    line = tmp_path / "l.wav"
    write_silence(line, 0.5)
    before = line.read_bytes()
    seconds, heard = trim_silence(line)
    assert heard is False and seconds == pytest.approx(0.5)
    assert line.read_bytes() == before


def test_the_cut_ends_are_faded_so_they_do_not_click(tmp_path: Path) -> None:
    line = tmp_path / "l.wav"
    write_tone(line, 1.0, padding=0.5)
    trim_silence(line)
    with wave.open(str(line), "rb") as source:
        raw = source.readframes(source.getnframes())
    first, last = (int.from_bytes(raw[i : i + 2], "little", signed=True) for i in (0, len(raw) - 2))
    assert abs(first) < 200 and abs(last) < 200  # the tone itself reaches about 6000


# --- joining lines into a track --------------------------------------------------------------


def test_a_line_that_runs_long_pushes_the_next_one_back_instead_of_overlapping(
    tmp_path: Path,
) -> None:
    first, second, third = (tmp_path / f"{n}.wav" for n in "abc")
    write_silence(first, 3.0)
    write_silence(second, 1.0)
    write_silence(third, 1.0)
    lines = [
        Placement(path=first, start=0.0),
        Placement(path=second, start=2.0),  # the first runs until 3.0
        Placement(path=third, start=10.0),  # plenty of room: back on time
    ]
    assert placed_starts(lines) == [0.0, 3.0, 10.0]

    track = tmp_path / "dialogue.wav"
    assemble_dialogue(lines, track)
    assert wav_seconds(track) == pytest.approx(11.0)
    with wave.open(str(track), "rb") as out:
        assert (out.getnchannels(), out.getsampwidth(), out.getframerate()) == (
            1,
            2,
            LINE_SAMPLE_RATE,
        )


def test_a_line_in_the_wrong_format_is_refused(tmp_path: Path) -> None:
    stereo = tmp_path / "stereo.wav"
    write_silence(stereo, 1.0, channels=2)
    with pytest.raises(ValueError, match="mono 16-bit"):
        assemble_dialogue([Placement(path=stereo, start=0.0)], tmp_path / "out.wav")


# --- the voice service connection ------------------------------------------------------------


def cartesia(
    handler: "httpx.MockTransport | None" = None, sleeps: list[float] | None = None
) -> CartesiaSynthesizer:
    sleeps = sleeps if sleeps is not None else []
    return CartesiaSynthesizer(
        "sk_car_secret",
        client=httpx.Client(transport=handler),
        sleep=sleeps.append,
    )


def test_a_line_is_requested_with_the_voice_language_speed_and_format(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"RIFFaudio")

    voice = cartesia(httpx.MockTransport(handler))
    dest = voice.synthesize(
        SynthesisRequest(text="مرحبا", voice_id="v-1", language="ar", speed=9.0), tmp_path / "a.wav"
    )
    assert dest.read_bytes() == b"RIFFaudio"
    request = seen[0]
    assert request.url.path == "/tts/bytes"
    assert request.headers["authorization"] == "Bearer sk_car_secret"
    assert request.headers["cartesia-version"]
    body = httpx.Response(200, content=request.content).json()
    assert body["transcript"] == "مرحبا"
    assert body["voice"] == {"id": "v-1"}
    assert body["language"] == "ar"
    assert body["generation_config"]["speed"] == 1.5  # never more than the service allows
    assert body["output_format"] == {
        "container": "wav",
        "encoding": "pcm_s16le",
        "sample_rate": LINE_SAMPLE_RATE,
    }


def test_a_voice_is_copied_from_a_recording(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"id": "voice-123"})

    sample = tmp_path / "sample.wav"
    write_silence(sample, 1.0)
    voice = cartesia(httpx.MockTransport(handler)).clone_voice(sample, "film-A", "en")
    assert (voice.id, voice.name, voice.language) == ("voice-123", "film-A", "en")
    assert seen[0].url.path == "/voices/clone"
    assert b'name="language"' in seen[0].content and b"film-A" in seen[0].content


def test_a_busy_service_is_retried_with_waits_in_between(tmp_path: Path) -> None:
    replies = iter([429, 503, 200])
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(next(replies), content=b"audio")

    voice = cartesia(httpx.MockTransport(handler), sleeps)
    voice.synthesize(SynthesisRequest(text="x", voice_id="v", language="es"), tmp_path / "a.wav")
    assert sleeps == [2.0, 4.0]


def test_running_out_of_credits_says_so_and_does_not_leak_the_key(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429)

    voice = cartesia(httpx.MockTransport(handler))
    with pytest.raises(QuotaExceededError) as raised:
        voice.synthesize(
            SynthesisRequest(text="x", voice_id="v", language="es"), tmp_path / "a.wav"
        )
    assert calls == 4
    assert "sk_car_secret" not in str(raised.value)
    assert "carries on" in str(raised.value)


@pytest.mark.parametrize("status", [401, 403])
def test_a_rejected_key_names_the_setting_to_fix(tmp_path: Path, status: int) -> None:
    voice = cartesia(httpx.MockTransport(lambda request: httpx.Response(status)))
    with pytest.raises(ProviderError, match="CARTESIA_API_KEY") as raised:
        voice.synthesize(SynthesisRequest(text="x", voice_id="v", language="es"), tmp_path / "a")
    assert "sk_car_secret" not in str(raised.value)


def test_a_refused_request_is_not_retried(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400)

    voice = cartesia(httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="400"):
        voice.synthesize(SynthesisRequest(text="x", voice_id="v", language="es"), tmp_path / "a")
    assert calls == 1


def test_cartesia_speaks_arabic_and_copies_voices() -> None:
    voice = cartesia()
    assert {"ar", "es", "en", "ur"} <= voice.languages()
    assert voice.supports_cloning


# --- translating for a dub -------------------------------------------------------------------


class RecordingGenerator(TextGenerator):
    name = "recording"

    def __init__(self) -> None:
        super().__init__()
        self.systems: list[str] = []
        self.prompts: list[str] = []

    def generate[T: BaseModel](self, system: str, prompt: str, schema: type[T]) -> T:
        self.systems.append(system)
        self.prompts.append(prompt)
        ids = [line[1 : line.index("]")] for line in prompt.splitlines() if line.startswith("[s")]
        return schema.model_validate({"lines": [{"id": i, "text": "x"} for i in ids]})


def test_a_dub_script_is_written_to_be_spoken_in_the_time_each_line_took() -> None:
    generator = RecordingGenerator()
    transcript = Transcript(language="en", segments=[seg("s0", 0, 2.34, "Hello there.")])
    Translator(generator).translate(transcript, "ar", for_dubbing=True)
    assert "[s0] (2.3s) Hello there." in generator.prompts[0]
    assert "spoken aloud" in generator.systems[0]
    # Arabic is named as Modern Standard, so a Modern Standard voice reads it naturally.
    assert "Modern Standard Arabic" in generator.prompts[0]


def test_subtitles_carry_no_timing_hints() -> None:
    generator = RecordingGenerator()
    transcript = Transcript(language="en", segments=[seg("s0", 0, 2, "Hello there.")])
    Translator(generator).translate(transcript, "es")
    assert "[s0] Hello there." in generator.prompts[0]
    assert "spoken aloud" not in generator.systems[0]


# --- the pipeline end to end -----------------------------------------------------------------


def spoken_texts(container: Container) -> list[str]:
    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)
    return [request.text for request in synthesizer.spoken]


def test_a_dub_is_made_and_added_as_an_audio_track(container: Container, source_file: Path) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))

    paths = container.store.paths(manifest)
    for artifact in (
        paths.dub_dialogue,
        paths.dub_background,
        paths.dub_transcript,
        paths.dub_translation("es"),
        paths.dub_voices,
        paths.dub_lines("es"),
        paths.audio_track("dub-es"),
    ):
        assert artifact.exists(), artifact
    assert not paths.dub_mix.exists()  # the whole sound is not kept once the voices are apart

    tracks = {t.id: t for t in manifest.audio_tracks}
    assert set(tracks) == {"original", "dub-es"}
    assert tracks["dub-es"].kind is TrackKind.DUB
    assert tracks["dub-es"].label == "Spanish dub"
    assert tracks["dub-es"].language == "es"
    assert manifest.choices is not None and manifest.choices.dub_languages == ["es"]
    assert all(r.status.value == "done" for r in manifest.stages.values())


def test_the_dub_is_spoken_in_a_copied_voice_per_speaker_at_the_original_times(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))

    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)
    assert synthesizer.cloned == [f"velvetdub-{manifest.title_id}-A"]  # the fake film has one voice
    assert {r.voice_id for r in synthesizer.spoken} == {f"clone-velvetdub-{manifest.title_id}-A"}
    assert {r.language for r in synthesizer.spoken} == {"es"}
    # Lines are recorded several at a time, so the order they finish in is not fixed.
    assert sorted(spoken_texts(container)) == [
        "[es] Hello there, friend.",
        "[es] What the hell is that?",
    ]
    assert [p.start for p in media.mix_calls[0]] == [1.0, 4.0]


def test_the_dub_is_transcribed_from_the_dialogue_alone_and_in_whole_sentences(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))
    paths = container.store.paths(manifest)
    # One audio extraction, of the separated dialogue. The film's own mix is never transcribed
    # for a dub alone: music under speech smears the timings, and it would be paid for twice.
    assert media.extract_calls == 1
    assert not paths.transcript.exists()
    assert [
        s.id for s in Transcript.model_validate_json(paths.dub_transcript.read_text()).segments
    ] == [
        "d0",
        "d1",
    ]


def test_a_second_run_costs_nothing(container: Container, source_file: Path) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    options = ProcessOptions(dub_languages=["es"])
    container.process(manifest, options)
    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)
    spoken, cloned = len(synthesizer.spoken), len(synthesizer.cloned)

    observer = RecordingObserver()
    container.process(manifest, options, observer)
    assert observer.started == []
    assert (len(synthesizer.spoken), len(synthesizer.cloned)) == (spoken, cloned)


def test_adding_a_second_language_reuses_the_voices_and_the_separation(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))
    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)
    before = len(synthesizer.spoken)

    observer = RecordingObserver()
    container.process(manifest, ProcessOptions(dub_languages=["es", "ar"]), observer)

    assert observer.started == ["dub_translate", "dub_speech", "dub_mix"]
    assert {"separate", "dub_transcribe", "dub_voices"} <= set(observer.skipped)
    assert len(synthesizer.cloned) == 1  # the same voices, not copied again
    new = synthesizer.spoken[before:]
    assert {r.language for r in new} == {"ar"}  # Spanish lines were not paid for again
    assert {t.id for t in manifest.audio_tracks} == {"original", "dub-es", "dub-ar"}


def test_editing_nothing_but_the_text_of_one_line_records_only_that_line(
    container: Container, source_file: Path
) -> None:
    from velvetdub.domain.translation import Translation
    from velvetdub.storage.artifacts import read_model, write_model

    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))
    paths = container.store.paths(manifest)
    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)
    before = len(synthesizer.spoken)

    translation = read_model(paths.dub_translation("es"), Translation)
    edited = translation.model_copy(
        update={
            "segments": [
                translation.segments[0].model_copy(update={"text": "Hola, amigo."}),
                translation.segments[1],
            ]
        }
    )
    write_model(paths.dub_translation("es"), edited)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))

    assert [r.text for r in synthesizer.spoken[before:]] == ["Hola, amigo."]
    assert len(list(paths.dub_line("es", "x").parent.glob("*.wav"))) == 2  # the old take is gone


class FailsOnce(FakeSynthesizer):
    """Fails the first time it is asked for one particular line, like a dropped connection."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self._text = text
        self.failed = False

    def synthesize(self, request: SynthesisRequest, dest: Path) -> Path:
        if request.text == self._text and not self.failed:
            self.failed = True
            raise QuotaExceededError("out of credits")
        return super().synthesize(request, dest)


def test_a_stopped_dub_resumes_without_paying_for_finished_lines_again(
    container: Container, source_file: Path
) -> None:
    container.settings = container.settings.model_copy(update={"tts_concurrency": 1})
    flaky = FailsOnce("[es] What the hell is that?")
    container.providers.synthesizer = flaky
    manifest = container.store.create("local", "Movie", source_file)
    options = ProcessOptions(dub_languages=["es"])

    with pytest.raises(StageFailedError):
        container.process(manifest, options)
    assert manifest.stages["dub_speech"].status.value == "failed"
    assert [r.text for r in flaky.spoken] == ["[es] Hello there, friend."]

    container.process(manifest, options)
    assert [r.text for r in flaky.spoken].count("[es] Hello there, friend.") == 1
    assert manifest.stages["dub_mix"].status.value == "done"


def test_a_film_is_not_dubbed_into_the_language_it_is_already_in(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["en"]))  # the fake film is English

    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)
    assert synthesizer.cloned == [] and synthesizer.spoken == []
    assert [t.id for t in manifest.audio_tracks] == ["original"]
    assert all(r.status.value == "done" for r in manifest.stages.values())


class Untouchable(FakeSynthesizer):
    def synthesize(self, request: SynthesisRequest, dest: Path) -> Path:
        raise AssertionError("nothing may be spoken when no dub is asked for")

    def clone_voice(self, sample: Path, name: str, language: str):  # type: ignore[no-untyped-def]
        raise AssertionError("no voice may be copied when no dub is asked for")


def test_without_a_dub_nothing_is_separated_spoken_or_copied(
    container: Container, source_file: Path
) -> None:
    container.providers.synthesizer = Untouchable()
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(subtitle_languages=["en"]))
    paths = container.store.paths(manifest)
    assert not paths.dub_stems.exists()
    assert [t.id for t in manifest.audio_tracks] == ["original"]


def test_a_dub_language_is_not_also_translated_as_subtitles(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))
    paths = container.store.paths(manifest)
    assert not paths.translation("es").exists()  # subtitles are chosen separately
    assert manifest.subtitle_tracks == []


def test_subtitles_and_a_dub_can_be_made_together(container: Container, source_file: Path) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(subtitle_languages=["en"], dub_languages=["ar"]))
    assert [t.language for t in manifest.subtitle_tracks] == ["en"]
    assert {t.id for t in manifest.audio_tracks} == {"original", "dub-ar"}


# --- the API ---------------------------------------------------------------------------------


def test_capabilities_list_the_languages_a_dub_can_be_made_in(container: Container) -> None:
    client = TestClient(create_app(container))
    assert client.get("/api/capabilities").json()["dub_languages"] == ["ar", "en", "es"]


def test_without_a_voice_service_key_dubbing_is_unavailable_and_says_so(
    container: Container, source_file: Path
) -> None:
    container.settings = container.settings.model_copy(update={"tts_provider": "cartesia"})
    container.providers = type(container.providers)(container.settings)
    client = TestClient(create_app(container), headers=CLIENT)
    assert client.get("/api/capabilities").json()["dub_languages"] == []

    manifest = container.store.create("local", "Movie", source_file)
    response = client.post(
        f"/api/titles/{manifest.title_id}/process", json={"dub_languages": ["es"]}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Dubbing isn't set up on this computer yet."


def test_a_language_the_voices_cannot_speak_is_refused_in_plain_words(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    client = TestClient(create_app(container), headers=CLIENT)
    response = client.post(
        f"/api/titles/{manifest.title_id}/process", json={"dub_languages": ["es", "ja"]}
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Dubbing can't speak Japanese."


def test_a_dub_can_be_asked_for_and_played(container: Container, source_file: Path) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    client = TestClient(create_app(container), headers=CLIENT)

    body = {"subtitle_languages": ["en"], "dub_languages": ["ar"]}
    assert client.post(f"/api/titles/{manifest.title_id}/process", json=body).status_code == 202
    assert wait_until_finished(client, manifest.title_id)["status"] == "done"

    title = client.get("/api/titles").json()[0]
    assert title["choices"]["dub_languages"] == ["ar"]

    playback = client.get(f"/api/titles/{manifest.title_id}/playback").json()
    tracks = {t["id"]: t for t in playback["audio_tracks"]}
    assert tracks["dub-ar"]["label"] == "Arabic dub"
    assert tracks["dub-ar"]["kind"] == "dub"
    audio = client.get(tracks["dub-ar"]["url"])
    assert audio.status_code == 200
    assert audio.content == b"fake-dub"


def test_progress_lists_every_dubbing_step(container: Container, source_file: Path) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    client = TestClient(create_app(container), headers=CLIENT)
    client.post(f"/api/titles/{manifest.title_id}/process", json={"dub_languages": ["es"]})
    state = wait_until_finished(client, manifest.title_id)
    stages = state["stages"]
    assert isinstance(stages, dict)
    assert list(stages)[-6:] == [
        "separate",
        "dub_transcribe",
        "dub_translate",
        "dub_voices",
        "dub_speech",
        "dub_mix",
    ]


# --- a pause survives all the way to the finished dub ----------------------------------------


class HeardUltron(FakeTranscriber):
    """Hears the Ultron line as the service really returned it: one segment, a stretched "me"."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        self.calls += 1
        return Transcript(language="en", segments=[ULTRON])


def test_the_two_halves_of_a_sentence_are_spoken_when_the_actor_says_them(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    container.providers.transcriber = HeardUltron()
    manifest = container.store.create("local", "Ultron", source_file)

    container.process(manifest, ProcessOptions(dub_languages=["es"]))

    assert sorted(spoken_texts(container)) == [
        "[es] But— Like the men said, what doesn't kill me",
        "[es] just makes me stronger.",
    ]
    # Placed at the original times: the second half comes after the silence, not straight after.
    assert [p.start for p in media.mix_calls[0]] == [44.24, 52.07]


def test_changing_the_sentence_rules_redoes_the_dub_without_transcribing_or_copying_again(
    container: Container, source_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    heard = HeardUltron()
    container.providers.transcriber = heard
    manifest = container.store.create("local", "Ultron", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))
    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)
    spoken_before = len(synthesizer.spoken)

    monkeypatch.setattr("velvetdub.pipeline.stages.dub_transcribe.RULES_VERSION", "sentences-next")
    observer = RecordingObserver()
    container.process(manifest, ProcessOptions(dub_languages=["es"]), observer)

    assert observer.started[:2] == ["dub_transcribe", "dub_translate"]
    assert heard.calls == 1  # what was heard is kept, so nothing was paid for twice
    assert len(synthesizer.cloned) == 1  # the same speaker, the same copied voice
    assert len(synthesizer.spoken) == spoken_before  # same words, same voice: nothing re-recorded


def test_a_voice_is_copied_again_only_when_there_is_a_new_speaker_or_service(
    container: Container, source_file: Path
) -> None:
    container.providers.transcriber = HeardUltron()
    manifest = container.store.create("local", "Ultron", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))
    paths = container.store.paths(manifest)
    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)

    from velvetdub.domain.dubbing import DubVoices
    from velvetdub.storage.artifacts import read_model, write_model

    voices = read_model(paths.dub_voices, DubVoices)
    write_model(paths.dub_voices, voices.model_copy(update={"provider": "cartesia:older-model"}))
    paths.dub_transcript.unlink()  # makes the script, and so the voices, be looked at again
    container.process(manifest, ProcessOptions(dub_languages=["es"]))
    assert len(synthesizer.cloned) == 2  # another service made them: copied afresh


def test_recordings_made_under_the_old_file_names_are_found_again(
    container: Container, source_file: Path
) -> None:
    from velvetdub.domain.dubbing import DubLines
    from velvetdub.storage.artifacts import read_model

    manifest = container.store.create("local", "Movie", source_file)
    options = ProcessOptions(dub_languages=["es"])
    container.process(manifest, options)
    paths = container.store.paths(manifest)
    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)
    before = len(synthesizer.spoken)

    # Put every recording back under the name earlier versions gave it: line id, then key.
    for line in read_model(paths.dub_lines("es"), DubLines).lines:
        (paths.root / line.path).rename(paths.dub_line("es", f"{line.segment_id}-{line.key}"))
    paths.dub_lines("es").unlink()

    container.process(manifest, options)
    assert len(synthesizer.spoken) == before  # found under their new names, not recorded again
    names = {p.name for p in paths.dub_line("es", "x").parent.glob("*.wav")}
    assert all("-" not in name for name in names)


# --- audio whose header cannot be trusted ----------------------------------------------------


def make_streamed(path: Path, seconds: float, padding: float = 0.0) -> None:
    """A WAV as streamed audio often arrives: the header states hours, not the real length."""
    write_tone(path, seconds, padding=padding)
    data = bytearray(path.read_bytes())
    data[4:8] = (0xFFFFFFFF).to_bytes(4, "little")  # the whole file's size
    data[data.find(b"data") + 4 : data.find(b"data") + 8] = (0xFFFFFFFF).to_bytes(4, "little")
    path.write_bytes(bytes(data))


def test_a_header_that_claims_hours_does_not_make_a_line_hours_long(tmp_path: Path) -> None:
    line = tmp_path / "l.wav"
    make_streamed(line, 1.0)
    assert wav_seconds(line) == pytest.approx(1.0, abs=0.01)  # not 89,000 seconds


def test_trimming_a_line_with_a_wrong_header_works_and_leaves_a_correct_one(tmp_path: Path) -> None:
    line = tmp_path / "l.wav"
    make_streamed(line, 1.0, padding=0.4)
    seconds, heard = trim_silence(line)  # used to fail: "'L' format requires 0 <= number"
    assert heard is True and seconds == pytest.approx(1.0 + 2 * 0.04, abs=0.02)
    with wave.open(str(line), "rb") as source:
        assert source.getnframes() == pytest.approx(seconds * LINE_SAMPLE_RATE, abs=2)  # honest now


def test_a_wrong_header_is_put_right_even_when_there_is_nothing_to_trim(tmp_path: Path) -> None:
    line = tmp_path / "l.wav"
    make_streamed(line, 1.0)  # no padding to cut
    trim_silence(line)
    with wave.open(str(line), "rb") as source:
        assert source.getnframes() == pytest.approx(1.0 * LINE_SAMPLE_RATE, abs=2)


def test_a_failure_while_trimming_never_leaves_a_recording_cut_short(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    line = tmp_path / "l.wav"
    write_tone(line, 1.0, padding=0.5)
    before = line.read_bytes()
    real_open: Any = wave.open

    def fail_when_writing(file: Any, mode: str = "rb") -> Any:
        if mode == "wb":
            raise OSError("the disk is full")
        return real_open(file, mode)

    monkeypatch.setattr("velvetdub.media.dialogue.wave.open", fail_when_writing)
    with pytest.raises(OSError, match="disk is full"):
        trim_silence(line)
    assert line.read_bytes() == before  # the recording is exactly as it was
    assert sorted(p.name for p in tmp_path.iterdir()) == ["l.wav"]  # and no stray file remains
