"""Keeping the crowd: the separator files crowds, chanting and singing under "dialogue", which a
dub replaces, so the original sound is kept wherever no actor is speaking, and the dub is made as
loud as the film. The last tests run the real ffmpeg on synthetic sound."""

import re
import shutil
import subprocess
import wave
from pathlib import Path

import pytest

from tests.conftest import FakeMediaTool
from tests.test_pipeline import RecordingObserver
from velvetdub.container import Container
from velvetdub.domain.dubbing import Ambience, AmbienceWindow, Placement
from velvetdub.domain.transcript import Segment
from velvetdub.features.dubbing.ambience import CROWD_DB, PAD, plan_ambience, speech_windows
from velvetdub.media.envelope import RAMP, RATE, write_gain_envelope
from velvetdub.media.tools import FFmpegMediaTool
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.providers.fake import write_silence


def seg(id_: str, start: float, end: float) -> Segment:
    return Segment(id=id_, start=start, end=end, text="x", speaker="A")


# --- where the actors speak ------------------------------------------------------------------


def test_speech_windows_leave_a_little_room_either_side_of_each_line() -> None:
    assert speech_windows([seg("a", 10.0, 12.0)]) == [(10.0 - PAD, 12.0 + PAD)]


def test_windows_that_touch_are_joined_and_the_first_never_starts_before_zero() -> None:
    windows = speech_windows([seg("b", 1.0, 2.0), seg("a", 0.05, 0.9), seg("c", 5.0, 6.0)])
    assert windows == [(0.0, 2.0 + PAD), (5.0 - PAD, 6.0 + PAD)]


# --- crowd scenes ----------------------------------------------------------------------------


def levels(loud_seconds: set[int], total: int = 60) -> list[float]:
    return [CROWD_DB + 10 if second in loud_seconds else CROWD_DB - 15 for second in range(total)]


def test_a_line_between_loud_gaps_gets_the_bed() -> None:
    windows = [(20.0, 26.0)]
    # The seconds before and after the line are loud and nobody is speaking: a crowd.
    planned = plan_ambience(windows, levels({17, 18, 27, 28}), bed=0.2)
    assert [(w.start, w.end, w.gain) for w in planned] == [(20.0, 26.0, 0.2)]


def test_an_ordinary_scene_gets_no_bed_so_there_is_no_ghost_of_the_actor() -> None:
    windows = [(20.0, 26.0)]
    assert [w.gain for w in plan_ambience(windows, levels(set()), bed=0.2)] == [0.0]


def test_loud_seconds_inside_other_lines_do_not_count_as_a_crowd() -> None:
    # Two lines close together: the actor's own voice is loud in the second line, which must not
    # make the first look like a crowd scene.
    windows = [(10.0, 12.0), (13.0, 20.0)]
    planned = plan_ambience(windows, levels(set(range(13, 21))), bed=0.2)
    assert [w.gain for w in planned] == [0.0, 0.0]


def test_a_crowd_only_a_few_seconds_away_does_not_count() -> None:
    windows = [(20.0, 22.0)]
    assert plan_ambience(windows, levels({10, 11, 40}), bed=0.2)[0].gain == 0.0


def test_the_bed_is_whatever_is_chosen_and_nothing_at_zero() -> None:
    windows = [(20.0, 26.0)]
    crowd = levels({18, 27})
    assert plan_ambience(windows, crowd, bed=0.5)[0].gain == 0.5
    assert plan_ambience(windows, crowd, bed=0.0)[0].gain == 0.0


def test_a_line_at_the_very_start_or_end_of_the_film_does_not_look_past_it() -> None:
    plan_ambience([(0.0, 2.0), (58.0, 59.9)], levels({3, 56}), bed=0.2)  # no error


# --- the volume curve ------------------------------------------------------------------------


def read_curve(path: Path) -> list[float]:
    with wave.open(str(path), "rb") as source:
        assert (source.getnchannels(), source.getsampwidth(), source.getframerate()) == (1, 2, RATE)
        raw = source.readframes(source.getnframes())
    return [
        int.from_bytes(raw[i : i + 2], "little", signed=True) / 32767 for i in range(0, len(raw), 2)
    ]


def test_the_curve_is_full_outside_a_window_and_the_gain_inside_it(tmp_path: Path) -> None:
    curve = tmp_path / "curve.wav"
    write_gain_envelope(curve, [AmbienceWindow(start=4.0, end=6.0, gain=0.25)], total_seconds=10)
    values = read_curve(curve)

    def at(seconds: float) -> float:
        return values[int(seconds * RATE)]

    assert at(1.0) == pytest.approx(1.0, abs=1e-3)
    assert at(4.0) == pytest.approx(0.25, abs=1e-3)
    assert at(5.5) == pytest.approx(0.25, abs=1e-3)
    assert at(5.999) == pytest.approx(0.25, abs=1e-3)
    assert at(8.0) == pytest.approx(1.0, abs=1e-3)
    assert len(values) == int(11 * RATE)  # the film plus a second


def test_the_volume_moves_in_the_gap_before_and_after_a_window_never_inside_it(
    tmp_path: Path,
) -> None:
    curve = tmp_path / "curve.wav"
    write_gain_envelope(curve, [AmbienceWindow(start=4.0, end=6.0, gain=0.0)], total_seconds=10)
    values = read_curve(curve)
    before = values[int((4.0 - RAMP) * RATE) : int(4.0 * RATE)]
    after = values[int(6.0 * RATE) : int((6.0 + RAMP) * RATE)]
    assert before == sorted(before, reverse=True) and before[0] > 0.9 and before[-1] < 0.05
    assert after == sorted(after) and after[0] < 0.05 and after[-1] > 0.9
    assert max(values[int(4.0 * RATE) : int(6.0 * RATE)]) == 0.0  # silent for the whole window


def test_two_windows_close_together_never_let_a_ramp_undo_the_silence(tmp_path: Path) -> None:
    curve = tmp_path / "curve.wav"
    windows = [
        AmbienceWindow(start=2.0, end=3.0, gain=0.0),
        AmbienceWindow(start=3.05, end=4.0, gain=0.0),
    ]
    write_gain_envelope(curve, windows, total_seconds=6)
    values = read_curve(curve)
    assert max(values[int(2.0 * RATE) : int(4.0 * RATE)]) < 0.5  # the gap between them stays low


# --- the stage -------------------------------------------------------------------------------


def test_the_dub_keeps_the_original_sound_between_lines_and_matches_the_films_loudness(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    media.levels = [-20.0] * 60  # loud all through: as if a crowd roars the whole time
    container.settings = container.settings.model_copy(update={"dub_crowd_bed": 0.2})
    manifest = container.store.create("local", "Movie", source_file)

    container.process(manifest, ProcessOptions(dub_languages=["es"]))

    ((ambience, loudness),) = media.mix_options
    paths = container.store.paths(manifest)
    assert ambience is not None and ambience.stem == paths.dub_dialogue
    # The fake film's two lines (1.0-3.0 s and 4.0-6.0 s), padded; the bed because a crowd is near.
    assert [(w.start, w.end) for w in ambience.windows] == [
        (1.0 - PAD, 3.0 + PAD),
        (4.0 - PAD, 6.0 + PAD),
    ]
    assert {w.gain for w in ambience.windows} == {0.2}
    assert loudness == -24.0  # the film's own loudness, not a fixed standard


def test_there_is_no_bed_under_the_lines_unless_it_is_asked_for(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    media.levels = [-20.0] * 60  # a crowd roars the whole time
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))
    ((ambience, _),) = media.mix_options
    assert ambience is not None
    assert {w.gain for w in ambience.windows} == {0.0}  # silent under every line: no voice behind


def test_keeping_the_crowd_can_be_turned_off(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    container.settings = container.settings.model_copy(update={"dub_keep_crowd": False})
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))
    ((ambience, loudness),) = media.mix_options
    assert ambience is None
    assert 1.0 not in media.level_steps  # the whole-second profile is only for the crowd
    assert loudness == -24.0  # matching the film's volume is separate from keeping the crowd


def test_a_silent_film_is_mixed_without_a_loudness_target(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    media.film_loudness = None
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(dub_languages=["es"]))
    assert media.mix_options[0][1] is None


def test_changing_how_much_is_kept_only_mixes_again_and_records_nothing_new(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    options = ProcessOptions(dub_languages=["es"])
    container.process(manifest, options)
    from velvetdub.providers.fake import FakeSynthesizer

    synthesizer = container.providers.synthesizer
    assert isinstance(synthesizer, FakeSynthesizer)
    spoken = len(synthesizer.spoken)

    container.settings = container.settings.model_copy(update={"dub_crowd_bed": 0.4})
    observer = RecordingObserver()
    container.process(manifest, options, observer)

    assert observer.started == ["dub_mix"]  # costs no voice credits: every line is already there
    assert len(synthesizer.spoken) == spoken
    assert len(media.mix_options) == 2


# --- the real ffmpeg -------------------------------------------------------------------------

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, capture_output=True, text=True)


def make_stem(path: Path, seconds: int = 8, volume_db: int = 0) -> None:
    """A steady tone in both channels: stands in for crowd noise in the dialogue stem."""
    run(
        "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
        f"sine=frequency=440:duration={seconds}:sample_rate=44100", "-af", f"volume={volume_db}dB",
        "-ac", "2", "-c:a", "pcm_s16le", str(path),
    )  # fmt: skip


def make_silence(path: Path, seconds: int = 8) -> None:
    run(
        "ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
        "anullsrc=r=44100:cl=stereo", "-t", str(seconds), "-c:a", "pcm_s16le", str(path),
    )  # fmt: skip


def mean_volume(path: Path, start: float, length: float) -> float:
    """Mean volume (dB) of a stretch of a file."""
    report = run(
        "ffmpeg", "-hide_banner", "-nostats", "-ss", str(start), "-t", str(length),
        "-i", str(path), "-af", "volumedetect", "-f", "null", "-",
    ).stderr  # fmt: skip
    return float(re.search(r"mean_volume: (-?[\d.]+) dB", report).group(1))  # type: ignore[union-attr]


@needs_ffmpeg
def test_the_real_mix_plays_the_original_between_lines_and_not_under_them(tmp_path: Path) -> None:
    stem, background, line = tmp_path / "stem.wav", tmp_path / "bg.wav", tmp_path / "line.wav"
    make_stem(stem)
    make_silence(background)
    write_silence(line, 1.0)  # the dub speaks, silently, so only the kept sound can be heard
    out = tmp_path / "dub.m4a"

    FFmpegMediaTool().mix_dub(
        [Placement(path=line, start=4.0)],
        background,
        out,
        ambience=Ambience(stem=stem, windows=(AmbienceWindow(start=3.0, end=6.0, gain=0.0),)),
        loudness=-30.0,
    )

    outside_before, inside, outside_after = (
        mean_volume(out, 0.3, 2.0),
        mean_volume(out, 3.4, 2.2),
        mean_volume(out, 6.5, 1.3),
    )
    assert outside_before > -50 and outside_after > -50  # the crowd is there between lines
    assert inside < -70  # and silent while the actor speaks
    assert not list(tmp_path.glob("*.volume.wav")) and not list(tmp_path.glob("*.partial*"))


@needs_ffmpeg
def test_the_real_mix_keeps_a_quiet_bed_under_a_line_in_a_crowd_scene(tmp_path: Path) -> None:
    stem, background, line = tmp_path / "stem.wav", tmp_path / "bg.wav", tmp_path / "line.wav"
    make_stem(stem)
    make_silence(background)
    write_silence(line, 1.0)
    out = tmp_path / "dub.m4a"

    FFmpegMediaTool().mix_dub(
        [Placement(path=line, start=4.0)],
        background,
        out,
        ambience=Ambience(stem=stem, windows=(AmbienceWindow(start=3.0, end=6.0, gain=0.1),)),
        loudness=-30.0,
    )

    outside, inside = mean_volume(out, 0.3, 2.0), mean_volume(out, 3.4, 2.2)
    assert outside - inside == pytest.approx(20.0, abs=2.5)  # a gain of 0.1 is -20 dB


@needs_ffmpeg
def test_the_real_mix_is_as_loud_as_the_film_it_was_asked_to_match(tmp_path: Path) -> None:
    stem, background, line = tmp_path / "stem.wav", tmp_path / "bg.wav", tmp_path / "line.wav"
    make_stem(stem, volume_db=-12)
    make_silence(background)
    write_silence(line, 1.0)
    tool = FFmpegMediaTool()
    for target in (-27.7, -18.0):
        out = tmp_path / f"dub{target}.m4a"
        tool.mix_dub(
            [Placement(path=line, start=4.0)],
            background,
            out,
            ambience=Ambience(stem=stem, windows=()),
            loudness=target,
        )
        measured = tool.measure_loudness(out)
        assert measured is not None
        assert measured == pytest.approx(target, abs=1.5)  # not boosted to a fixed -16


@needs_ffmpeg
def test_the_real_mix_still_works_without_the_crowd_or_a_loudness_target(tmp_path: Path) -> None:
    background, line = tmp_path / "bg.wav", tmp_path / "line.wav"
    make_stem(background)
    write_silence(line, 1.0)
    out = tmp_path / "dub.m4a"
    FFmpegMediaTool().mix_dub([Placement(path=line, start=1.0)], background, out)
    assert out.stat().st_size > 1000


@needs_ffmpeg
def test_the_real_level_profile_reads_one_level_for_each_second(tmp_path: Path) -> None:
    tone, quiet, both = tmp_path / "tone.wav", tmp_path / "quiet.wav", tmp_path / "both.wav"
    make_stem(tone, seconds=2)
    make_silence(quiet, seconds=2)
    run(
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(tone), "-i", str(quiet),
        "-filter_complex", "[0][1]concat=n=2:v=0:a=1", "-c:a", "pcm_s16le", str(both),
    )  # fmt: skip
    readings = FFmpegMediaTool().level_profile(both)
    assert len(readings) == 4
    assert readings[0] > -30 and readings[1] > -30
    assert readings[2] <= -100 and readings[3] <= -100  # silence reads very low, not minus infinity
    assert all(isinstance(r, float) and r > float("-inf") for r in readings)


@needs_ffmpeg
def test_the_real_level_profile_can_read_finer_than_a_second(tmp_path: Path) -> None:
    tone, quiet, both = tmp_path / "tone.wav", tmp_path / "quiet.wav", tmp_path / "both.wav"
    make_stem(tone, seconds=2)
    make_silence(quiet, seconds=2)
    run(
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(tone), "-i", str(quiet),
        "-filter_complex", "[0][1]concat=n=2:v=0:a=1", "-c:a", "pcm_s16le", str(both),
    )  # fmt: skip
    readings = FFmpegMediaTool().level_profile(both, 0.5)
    assert len(readings) == 8  # four seconds, a reading every half second
    assert all(r > -30 for r in readings[:4]) and all(r <= -100 for r in readings[4:])
