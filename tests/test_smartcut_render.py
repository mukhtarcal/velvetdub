"""The smart cut on real encoded video: right frames, right place, copied where it should be,
sound and picture still in step. Needs ffmpeg."""

import array
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from velvetdub.domain.export import EditPlan, plan_edit
from velvetdub.domain.filtering import (
    FilterAction,
    FilterCategory,
    FilterEvent,
    ResolvedFilter,
    Severity,
)
from velvetdub.media.smartcut import probe_for_smart_cut
from velvetdub.media.tools import FFmpegMediaTool

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")

SECONDS = 40


def run(*command: str) -> str:
    done = subprocess.run(command, check=True, capture_output=True, text=True)
    return done.stdout + done.stderr


def make_film(
    path: Path,
    *,
    fps: str = "25",
    bframes: int = 3,
    codec: str = "libx264",
    audio: bool = True,
    delay: float = 0.0,
) -> None:
    """A busy picture (so a wrong frame is easy to see) with keyframes every 2 s."""
    rate = eval(fps.replace("/", "/ "))
    command = ["ffmpeg", "-y", "-loglevel", "error"]
    command += ["-f", "lavfi", "-i", f"testsrc2=size=320x180:rate={fps}:duration={SECONDS}"]
    if audio:
        command += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={SECONDS}"]
    if (
        delay
    ):  # the picture starts this much after the sound, like a real file whose first frame is late
        command += ["-vf", f"setpts=PTS+{delay}/TB"]
    command += ["-c:v", codec, "-pix_fmt", "yuv420p"]
    if codec == "libx264":
        gop = round(rate * 2)
        command += [
            "-g",
            str(gop),
            "-keyint_min",
            str(gop),
            "-sc_threshold",
            "0",
            "-bf",
            str(bframes),
        ]
        command += ["-x264-params", "open-gop=0"]
    if audio:
        command += ["-c:a", "aac", "-shortest"]
    run(*command, str(path))


def cut_plan(cuts: list[tuple[float, float]], words: list[tuple[float, float]]) -> EditPlan:
    """Scenes to skip and words to mute, as the player would act on them."""

    def resolved(start: float, end: float, action: FilterAction) -> ResolvedFilter:
        event = FilterEvent(
            id=f"{start}",
            category=FilterCategory.NUDITY,
            severity=Severity.STRONG,
            start=start,
            end=end,
            source="t",
        )
        return ResolvedFilter(event=event, action=action)

    filters = [resolved(a, b, FilterAction.SKIP) for a, b in cuts]
    filters += [resolved(a, b, FilterAction.MUTE) for a, b in words]
    return plan_edit(filters, float(SECONDS))


def to_copy_time(plan: EditPlan, film_time: float) -> float:
    """Where a moment of the film falls in the cleaned copy: the kept time before it."""
    return sum(min(end, film_time) - start for start, end in plan.keep if film_time > start)


def frame_times(path: Path) -> list[float]:
    out = run(
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "frame=best_effort_timestamp_time", "-of", "csv=p=0", str(path),
    )  # fmt: skip
    return sorted(float(x.strip(",")) for x in out.split() if x.strip(","))


def start_time(path: Path, stream: str) -> float:
    out = run(
        "ffprobe", "-v", "error", "-select_streams", stream,
        "-show_entries", "stream=start_time", "-of", "csv=p=0", str(path),
    )  # fmt: skip
    return float(out.strip())


def duration(path: Path, stream: str) -> float:
    out = run(
        "ffprobe", "-v", "error", "-select_streams", stream,
        "-show_entries", "stream=duration", "-of", "csv=p=0", str(path),
    )  # fmt: skip
    return float(out.strip())


def expected_frames(source: Path, plan: EditPlan) -> list[int]:
    """Which source frames should survive, found independently of the code under test: a frame
    stays if its time falls inside a kept stretch."""
    times = frame_times(source)
    return [i for i, t in enumerate(times) if any(start <= t < end for start, end in plan.keep)]


def similarity(source: Path, copy: Path, kept: list[int], fps: float) -> list[float]:
    """SSIM of each output frame against the source frame it should be. Both sides are put on the
    same clock, one tick per frame, so a frame is only ever compared with its own counterpart."""
    numbers = "+".join(f"eq(n,{n})" for n in kept)
    log = copy.with_suffix(".ssim.log")
    tick = round(1_000_000 / fps)
    graph = (
        f"[0:v]select='{numbers}',settb=1/1000000,setpts=N*{tick}[a];"
        f"[1:v]settb=1/1000000,setpts=N*{tick}[b];[a][b]ssim=stats_file={log}"
    )
    run("ffmpeg", "-loglevel", "error", "-i", str(source), "-i", str(copy),
        "-filter_complex", graph, "-f", "null", "-")  # fmt: skip
    return [float(re.search(r"All:(\S+)", line)[1]) for line in log.read_text().splitlines()]  # type: ignore[index]


def picture_hashes(path: Path) -> list[str]:
    """A fingerprint of every decoded frame, in order."""
    # passthrough: every decoded frame, none dropped or repeated to even out the timestamps
    out = run("ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0",
              "-fps_mode", "passthrough", "-f", "framemd5", "-")  # fmt: skip
    return [line.split(",")[-1].strip() for line in out.splitlines() if line and line[0] != "#"]


@pytest.fixture(
    params=[(0, "25", 0.0), (3, "25", 0.0), (3, "24000/1001", 0.0), (3, "24000/1001", 0.083417)],
    ids=["no-bframes", "bframes", "ntsc", "starts-late"],
)
def film(request: pytest.FixtureRequest, tmp_path: Path) -> Path:
    bframes, fps, delay = request.param
    path = tmp_path / "film.mp4"
    make_film(path, fps=fps, bframes=bframes, delay=delay)
    return path


PLAN = cut_plan(cuts=[(7.3, 11.9), (23.05, 23.4), (30.0, 31.7)], words=[(15.0, 15.5), (35.2, 35.6)])


def render(source: Path, dest: Path, plan: EditPlan = PLAN) -> list[float]:
    progress: list[float] = []
    FFmpegMediaTool().render_cleaned(source, dest, plan, progress.append)
    return progress


def test_the_smart_cut_keeps_exactly_the_right_frames_in_the_right_places(
    film: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out" / "cleaned.mp4"
    progress = render(film, out)
    assert [p.name for p in out.parent.iterdir()] == ["cleaned.mp4"]  # no scraps left

    kept = expected_frames(film, PLAN)
    assert len(frame_times(out)) == len(kept)

    steps = [b - a for a, b in zip(frame_times(out), frame_times(out)[1:], strict=False)]
    assert max(steps) - min(steps) < 0.002  # no gap or jump where pieces were joined

    fps = len(frame_times(film)) / SECONDS
    scores = similarity(film, out, kept, fps)
    assert len(scores) == len(kept)
    assert min(scores) > 0.95  # every frame is the one it should be
    # the stretches copied from the source are the source, bit for bit
    original = picture_hashes(film)
    identical = sum(1 for h, n in zip(picture_hashes(out), kept, strict=True) if h == original[n])
    assert identical > len(kept) * 0.7

    assert progress == sorted(progress) and progress[-1] == 1.0


def test_sound_and_picture_end_together_and_the_mutes_are_silent(
    film: Path, tmp_path: Path
) -> None:
    out = tmp_path / "cleaned.mp4"
    render(film, out)
    assert duration(out, "a:0") == pytest.approx(duration(out, "v:0"), abs=0.06)
    # the film is 40 s; the plan removes 4.6 + 0.35 + 1.7 s
    # the plan's times are exact, but cuts fall on whole frames: up to a frame per cut either way
    assert duration(out, "v:0") == pytest.approx(SECONDS - PLAN.removed, abs=0.15)

    for word_start, word_end in [(15.0, 15.5), (35.2, 35.6)]:
        middle = to_copy_time(PLAN, (word_start + word_end) / 2)
        assert mean_volume(out, middle - 0.1, 0.2) < -60, f"the word at {word_start} s is audible"
    assert mean_volume(out, to_copy_time(PLAN, 12.5), 0.5) > -35  # the tone elsewhere is untouched
    assert mean_volume(out, to_copy_time(PLAN, 26.0), 0.5) > -35


def mean_volume(path: Path, start: float, length: float) -> float:
    log = run("ffmpeg", "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(path),
              "-af", "volumedetect", "-vn", "-f", "null", "-")  # fmt: skip
    found = re.search(r"mean_volume: (-?[\d.]+|-inf) dB", log)
    assert found, log
    return float("-inf") if found[1] == "-inf" else float(found[1])


def test_the_smart_cut_was_used_and_the_slow_path_was_not(
    film: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*_: object) -> None:
        raise AssertionError("the whole film was encoded again")

    monkeypatch.setattr(FFmpegMediaTool, "_render_full", forbidden)
    render(film, tmp_path / "cleaned.mp4")


# --- lip sync ----------------------------------------------------------------------------


def make_flash_film(path: Path, delay: float = 0.0) -> None:
    """Black picture and silence, except for a white flash and a loud tone together at 30 s."""
    video = f"color=c=black:size=160x90:rate=25:duration={SECONDS}"
    video += ",drawbox=x=0:y=0:w=160:h=90:color=white:t=fill:enable='between(t,30,30.4)'"
    audio = f"sine=frequency=1000:duration={SECONDS},volume='if(between(t,30,30.4),1,0)':eval=frame"
    command = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", video]
    command += ["-f", "lavfi", "-i", audio]
    if delay:  # the picture starts this much after the sound
        command += ["-vf", f"setpts=PTS+{delay}/TB"]
    command += ["-c:v", "libx264", "-g", "50", "-keyint_min", "50"]
    command += ["-sc_threshold", "0", "-bf", "3", "-pix_fmt", "yuv420p", "-c:a", "aac"]
    run(*command, "-shortest", str(path))


def flash_and_tone(path: Path) -> tuple[float, float]:
    """When the white flash and the loud tone first appear, in seconds on the file's clock."""
    gray = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), "-vf", "scale=1:1,format=gray",
         "-fps_mode", "passthrough", "-f", "rawvideo", "-"], check=True, capture_output=True,
    ).stdout  # fmt: skip
    first = next(i for i, level in enumerate(gray) if level > 128)
    picture = frame_times(path)[first]
    pcm = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "8000",
         "-f", "s16le", "-"], check=True, capture_output=True,
    ).stdout  # fmt: skip
    samples = array.array("h")
    samples.frombytes(pcm)
    onset = next(i for i, s in enumerate(samples) if abs(s) > 3000)
    return picture, onset / 8000 + start_time(path, "a:0")


@pytest.mark.parametrize(
    "delay", [0.0, 0.083417, 0.5], ids=["in-step", "starts-like-the-wolf", "picture-starts-late"]
)
def test_picture_and_sound_keep_their_offset_after_cutting(tmp_path: Path, delay: float) -> None:
    source = tmp_path / "flash.mp4"
    make_flash_film(source, delay=delay)
    before_picture, before_sound = flash_and_tone(source)
    offset = before_picture - before_sound  # the film's own: 0, or the late start

    plan = cut_plan(cuts=[(5.3, 9.9), (14.05, 16.0)], words=[])
    out = tmp_path / "cleaned.mp4"
    render(source, out, plan)
    after_picture, after_sound = flash_and_tone(out)

    # the flash moved earlier by the (frame-aligned) time cut before it...
    assert after_picture - before_picture == pytest.approx(-6.52, abs=0.01)
    # ...and the sound kept exactly the same distance from the picture as in the film
    assert (after_picture - after_sound) == pytest.approx(offset, abs=0.005)  # well under a frame


# --- what it will and will not do --------------------------------------------------------


def test_a_film_without_sound_still_works(tmp_path: Path) -> None:
    source = tmp_path / "silent.mp4"
    make_film(source, audio=False)
    out = tmp_path / "cleaned.mp4"
    render(source, out)
    assert len(frame_times(out)) == len(expected_frames(source, PLAN))
    streams = run(
        "ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)
    )
    assert streams.split() == ["video"]


def test_a_film_that_is_not_ordinary_h264_is_encoded_the_slow_way_and_still_right(
    tmp_path: Path,
) -> None:
    source = tmp_path / "other.mp4"
    make_film(source, codec="mpeg4")
    assert probe_for_smart_cut("ffprobe", source) is None
    out = tmp_path / "cleaned.mp4"
    render(source, out)
    assert duration(out, "v:0") == pytest.approx(SECONDS - PLAN.removed, abs=0.1)


def test_probing_finds_the_frame_grid_and_the_keyframes(tmp_path: Path) -> None:
    source = tmp_path / "film.mp4"
    make_film(source, fps="25", bframes=3)
    info = probe_for_smart_cut("ffprobe", source)
    assert info is not None
    assert info.timing.frame_count == 25 * SECONDS
    assert info.timing.frame_duration == pytest.approx(0.04)
    assert info.keyframes == list(range(0, 25 * SECONDS, 50))  # one every two seconds
    assert info.has_audio is True
    assert info.timing.start == pytest.approx(0.0, abs=0.001)


def test_probing_finds_where_the_picture_starts_when_it_is_not_at_zero(tmp_path: Path) -> None:
    source = tmp_path / "late.mp4"
    make_film(source, fps="25", bframes=3, delay=0.5)
    info = probe_for_smart_cut("ffprobe", source)
    assert info is not None
    assert info.timing.start == pytest.approx(0.48, abs=0.001)  # 0.5 s, on the 25 fps grid
    assert info.timing.frame_count == round(
        25 * (SECONDS - 0.48)
    )  # the film is cut short to the sound


def test_a_failed_render_leaves_nothing_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "film.mp4"
    make_film(source)
    out = tmp_path / "out" / "cleaned.mp4"
    real_run = subprocess.run
    calls = {"n": 0}

    def flaky(command: list[str], *args: object, **kwargs: object) -> object:
        if "-output_ts_offset" in command:
            calls["n"] += 1
            if calls["n"] == 2:
                raise subprocess.CalledProcessError(1, command, stderr="boom")
        return real_run(command, *args, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(subprocess, "run", flaky)
    with pytest.raises(subprocess.CalledProcessError):
        render(source, out)
    assert list(out.parent.iterdir()) == []


def test_work_left_by_a_stopped_render_is_cleared_on_the_next_one(tmp_path: Path) -> None:
    source = tmp_path / "film.mp4"
    make_film(source)
    out = tmp_path / "out" / "cleaned.mp4"
    stale = out.parent / "work-deadbeef"
    stale.mkdir(parents=True)
    (stale / "video.ts").write_bytes(b"x" * 1000)
    render(source, out)
    assert [p.name for p in out.parent.iterdir()] == ["cleaned.mp4"]
