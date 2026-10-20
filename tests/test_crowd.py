"""Crowd chants are left as the film has them instead of being dubbed, and lines the voice got
badly wrong are tried again. The countdown in the Wolf of Wall Street test is the model: the
service wrote "One!", "2!" and "3!" as brief words (and missed "Two"), each for a different
speaker, while the sound is three loud bursts a second or more long."""

from pathlib import Path

import pytest

from tests.conftest import FakeMediaTool
from velvetdub.container import Container
from velvetdub.domain.dubbing import DubLine, DubLines, DubVoices
from velvetdub.domain.transcript import Segment, Transcript, Word
from velvetdub.domain.translation import TranslatedSegment, Translation
from velvetdub.features.dubbing.crowd import STEP, crowd_burst, crowd_lines
from velvetdub.features.dubbing.lines import record_lines
from velvetdub.features.dubbing.speech import LineRecorder
from velvetdub.media.dialogue import wav_seconds
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.providers.fake import FakeSynthesizer, FakeTranscriber, write_tone
from velvetdub.storage.artifacts import read_model

QUIET = -60.0


def readings(seconds: float, bursts: dict[tuple[float, float], float]) -> list[float]:
    """A loudness reading every 0.1 s: quiet, except in the bursts given as (start, end): dB."""
    levels = [QUIET] * int(seconds / STEP)
    for (start, end), db in bursts.items():
        for i in range(int(start / STEP), int(end / STEP)):
            levels[i] = db
    return levels


# The real countdown: "One" 26.7-27.8, "Two" 28.5-29.5 (never transcribed), "Three" 30.2-32.0.
COUNTDOWN = readings(40, {(26.7, 27.8): -20.0, (28.5, 29.5): -21.0, (30.2, 32.0): -17.0})


# --- what a chant is -------------------------------------------------------------------------


def test_a_brief_word_inside_a_long_loud_burst_is_a_chant() -> None:
    assert crowd_burst(26.87, 27.00, COUNTDOWN)  # "One!": 0.13 s of words, a 1.1 s roar


def test_a_word_at_the_very_edge_of_its_burst_still_belongs_to_it() -> None:
    # "2!" was placed at 30.19-30.24, in the silence just before the "Three" burst begins.
    assert crowd_burst(30.19, 30.24, COUNTDOWN)
    assert crowd_burst(30.30, 30.72, COUNTDOWN)  # "3!"


def test_a_quiet_burst_is_just_the_room_however_long_it_lasts() -> None:
    noisy_room = readings(40, {(10.0, 16.0): -42.0})
    assert not crowd_burst(12.0, 12.1, noisy_room)  # a quiet "Thank you." in a noisy room


def test_a_person_talking_is_not_a_chant_however_loud() -> None:
    shouting = readings(40, {(10.0, 14.0): -20.0})
    assert not crowd_burst(10.0, 13.5, shouting)  # 3.5 s of words: a line, not a shout


def test_a_loud_word_that_is_only_as_long_as_the_word_is_a_shout_not_a_chant() -> None:
    shout = readings(40, {(10.0, 10.5): -20.0})
    assert not crowd_burst(10.05, 10.4, shout)  # the burst is the word itself


def test_nothing_is_a_chant_when_the_sound_was_not_measured() -> None:
    assert not crowd_burst(26.87, 27.00, [])


def test_a_word_past_the_end_of_the_readings_is_not_an_error() -> None:
    assert not crowd_burst(500.0, 500.2, COUNTDOWN)


def seg(id_: str, start: float, end: float, text: str, speaker: str = "A") -> Segment:
    return Segment(id=id_, start=start, end=end, text=text, speaker=speaker)


def test_every_chanted_word_of_the_countdown_is_found_and_the_real_line_is_not() -> None:
    segments = [
        seg("d0", 26.87, 27.00, "One!", "D"),
        seg("d1", 30.19, 30.24, "2!", "B"),
        seg("d2", 30.30, 30.72, "3!", "A"),
        seg("d3", 32.23, 33.60, "My name is Jordan Belfort.", "E"),
    ]
    assert crowd_lines(segments, COUNTDOWN) == {"d0", "d1", "d2"}


# --- lines left as the film has them ---------------------------------------------------------


def words(*items: tuple[str, float, float]) -> tuple[Word, ...]:
    return tuple(Word(text=t, start=a, end=b) for t, a, b in items)


class HeardCountdown(FakeTranscriber):
    """The countdown as the service wrote it, then a real line."""

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        return Transcript(
            language="en",
            segments=[
                Segment(id="s0", start=26.87, end=27.0, text="One!", speaker="D",
                        words=words(("One!", 26.87, 27.0))),
                Segment(id="s1", start=30.19, end=30.24, text="2!", speaker="B",
                        words=words(("2!", 30.19, 30.24))),
                Segment(id="s2", start=30.30, end=30.72, text="3!", speaker="A",
                        words=words(("3!", 30.30, 30.72))),
                Segment(id="s3", start=32.23, end=33.6, text="My name is Jordan Belfort.",
                        speaker="E", words=words(("My name is Jordan Belfort.", 32.23, 33.6))),
            ],
        )  # fmt: skip


def test_a_chant_is_not_dubbed_and_the_original_crowd_plays_there(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    container.providers.transcriber = HeardCountdown()
    media.fine_levels = COUNTDOWN
    media.levels = [-50.0] * 40  # the one-second profile: nothing for the crowd bed to hold on to
    manifest = container.store.create("local", "Wolf", source_file)

    container.process(manifest, ProcessOptions(dub_languages=["es"]))

    paths = container.store.paths(manifest)
    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)
    # Only the real line was spoken: no cloned voice shouting "¡Uno!", "¡Dos!" and "¡Tres!".
    assert [r.text for r in synthesizer.spoken] == ["[es] My name is Jordan Belfort."]
    lines = read_model(paths.dub_lines("es"), DubLines)
    assert [line.text for line in lines.lines] == ["[es] My name is Jordan Belfort."]
    assert lines.kept_original == ["d0", "d1", "d2"]
    # So the original silences only around the real line, and the chants play as the film has them.
    ((ambience, _),) = media.mix_options
    assert ambience is not None
    assert [(round(w.start, 2), round(w.end, 2)) for w in ambience.windows] == [(32.08, 33.75)]
    assert [p.start for p in media.mix_calls[0]] == [32.23]
    assert media.level_steps[0] == STEP  # the sound was measured finely enough to see a chant


# --- trying a line again, once ---------------------------------------------------------------


def one_line(text: str = "yo") -> tuple[Transcript, Translation, DubVoices]:
    transcript = Transcript(language="en", segments=[seg("d0", 35.52, 35.62, "Me.")])
    translation = Translation(
        language="es",
        segments=[TranslatedSegment(segment_id="d0", text=text, target_duration=0.1)],
    )
    return transcript, translation, DubVoices(provider="fake:default", voices={"A": "voice-a"})


def run_record(
    tmp_path: Path,
    synthesizer: FakeSynthesizer,
    media: FakeMediaTool,
    previous: DubLines | None = None,
    skip: set[str] | None = None,
) -> DubLines:
    transcript, translation, voices = one_line()
    return record_lines(
        transcript=transcript,
        translation=translation,
        voices=voices,
        film_seconds=60.0,
        recorder=LineRecorder(synthesizer, media),
        identity="fake:default",
        line_path=lambda name: tmp_path / "lines" / f"{name}.wav",
        relative=lambda path: path.relative_to(tmp_path).as_posix(),
        concurrency=1,
        skip=skip or set(),
        previous=previous,
    )


def test_a_recording_that_clearly_does_not_fit_is_asked_for_again_once(
    tmp_path: Path, media: FakeMediaTool
) -> None:
    synthesizer = FakeSynthesizer()
    synthesizer.plan = [0.4]
    first = run_record(tmp_path, synthesizer, media)
    (line,) = first.lines
    assert line.takes == 1 and len(synthesizer.spoken) == 1

    # As if recorded before takes were counted, and stretched far past its 0.5 s room.
    path = tmp_path / line.path
    write_tone(path, 3.0)
    legacy = DubLines(language="es", lines=[line.model_copy(update={"takes": 0})])

    synthesizer.plan = [0.4]
    healed = run_record(tmp_path, synthesizer, media, previous=legacy)
    assert len(synthesizer.spoken) == 2  # asked again
    assert wav_seconds(tmp_path / healed.lines[0].path) == pytest.approx(0.4, abs=0.1)
    assert healed.lines[0].takes >= 1

    # Once only: if it is still long, a recording that has been tried again is left as it is.
    write_tone(tmp_path / healed.lines[0].path, 3.0)
    run_record(tmp_path, synthesizer, media, previous=healed)
    assert len(synthesizer.spoken) == 2


def test_a_recording_that_is_only_a_little_long_is_left_alone(
    tmp_path: Path, media: FakeMediaTool
) -> None:
    synthesizer = FakeSynthesizer()
    synthesizer.plan = [0.4]
    (line,) = run_record(tmp_path, synthesizer, media).lines
    write_tone(tmp_path / line.path, 0.7)  # 0.2 s over a 0.5 s room: squeezing copes with that
    legacy = DubLines(language="es", lines=[line.model_copy(update={"takes": 0})])
    run_record(tmp_path, synthesizer, media, previous=legacy)
    assert len(synthesizer.spoken) == 1


def test_an_older_recording_has_its_silence_trimmed_without_being_recorded_again(
    tmp_path: Path, media: FakeMediaTool
) -> None:
    synthesizer = FakeSynthesizer()
    synthesizer.plan = [0.4]
    (line,) = run_record(tmp_path, synthesizer, media).lines
    write_tone(tmp_path / line.path, 0.4, padding=0.3)  # padded, as recordings used to be
    legacy = DubLines(language="es", lines=[line.model_copy(update={"takes": 0})])
    (trimmed,) = run_record(tmp_path, synthesizer, media, previous=legacy).lines
    assert len(synthesizer.spoken) == 1
    assert trimmed.duration == pytest.approx(0.4 + 0.08, abs=0.02)  # not 1.0


def test_a_line_the_voice_could_not_say_is_left_as_the_film_has_it(
    tmp_path: Path, media: FakeMediaTool
) -> None:
    synthesizer = FakeSynthesizer()
    synthesizer.plan = [0, 0, 0, 0]
    result = run_record(tmp_path, synthesizer, media)
    assert result.lines == [] and result.kept_original == ["d0"]


def test_a_skipped_line_costs_nothing_and_is_listed_as_kept(
    tmp_path: Path, media: FakeMediaTool
) -> None:
    synthesizer = FakeSynthesizer()
    result = run_record(tmp_path, synthesizer, media, skip={"d0"})
    assert synthesizer.spoken == []
    assert result.lines == [] and result.kept_original == ["d0"]


def test_a_line_records_how_many_times_it_was_asked_for() -> None:
    assert (
        DubLine(
            segment_id="d0", start=0, slot=1, text="x", voice_id="v", key="k", duration=1, path="p"
        ).takes
        == 0
    )  # older records had no count
