"""Dubbing: the rules (sentences, room, samples, fitting), the voice service connection, the
pipeline end to end on fakes, and the API. No network, keys, Demucs or ffmpeg needed."""

import wave
from pathlib import Path

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
from velvetdub.domain.transcript import Segment, Transcript
from velvetdub.errors import ProviderError, QuotaExceededError, StageFailedError
from velvetdub.features.dubbing.cast import clone_cast
from velvetdub.features.dubbing.samples import plan_cast
from velvetdub.features.dubbing.sentences import merge_sentences
from velvetdub.features.dubbing.speech import LineRecorder
from velvetdub.features.dubbing.timing import slots
from velvetdub.features.translation.translator import Translator
from velvetdub.media.dialogue import assemble_dialogue, placed_starts, wav_seconds
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.providers.base import TextGenerator
from velvetdub.providers.cartesia import CartesiaSynthesizer
from velvetdub.providers.fake import FakeSynthesizer, write_silence

# --- the rules -------------------------------------------------------------------------------


def seg(id_: str, start: float, end: float, text: str, speaker: str | None = "A") -> Segment:
    return Segment(id=id_, start=start, end=end, text=text, speaker=speaker)


def test_an_unfinished_line_joins_the_next_one_from_the_same_speaker() -> None:
    transcript = Transcript(
        language="en",
        segments=[
            seg("s0", 97.2, 98.3, "we are"),  # a long dramatic pause, but the thought isn't done
            seg("s1", 100.8, 102.8, "going to need a miracle."),
        ],
    )
    merged = merge_sentences(transcript).segments
    assert len(merged) == 1
    assert merged[0].id == "d0"
    assert (merged[0].start, merged[0].end) == (97.2, 102.8)
    assert merged[0].text == "we are going to need a miracle."


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
    speed, seconds = lines.record("x" * 20, "v", "es", 3.0, tmp_path / "l.wav")  # 1.0 s
    assert speed == 1.0
    assert seconds == pytest.approx(1.0)
    assert len(synthesizer.spoken) == 1
    assert media.tempo_calls == []


def test_a_long_line_is_asked_for_faster_before_anything_is_squeezed(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, synthesizer = recorder(media)
    _, seconds = lines.record("x" * 100, "v", "es", 4.0, tmp_path / "l.wav")  # 5.0 s at 1.0
    assert [r.speed for r in synthesizer.spoken] == [1.0, pytest.approx(5.0 / 4.0 * 1.02)]
    assert seconds <= 4.0 + 0.05
    assert media.tempo_calls == []


def test_the_last_resort_squeezes_the_recording_by_a_little(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, synthesizer = recorder(media)
    _, seconds = lines.record("x" * 100, "v", "es", 3.0, tmp_path / "l.wav")
    assert synthesizer.spoken[-1].speed == 1.5  # as fast as the service goes
    assert len(media.tempo_calls) == 1 and 1.0 < media.tempo_calls[0] <= 1.2
    assert seconds == pytest.approx(3.0, abs=0.05)


def test_a_line_that_cannot_be_made_to_fit_is_kept_not_cut(
    media: FakeMediaTool, tmp_path: Path
) -> None:
    lines, _ = recorder(media)
    _, seconds = lines.record("x" * 200, "v", "es", 2.0, tmp_path / "l.wav")
    assert seconds > 2.0  # the dub pushes the next line back instead


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
    assert spoken_texts(container) == ["[es] Hello there, friend.", "[es] What the hell is that?"]
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
