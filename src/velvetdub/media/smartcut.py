"""Rendering a cleaned copy with a smart cut (planning is in `domain/smartcut.py`).

Picture: whole stretches between keyframes are copied from the source untouched, and only the
partial stretch at each end of a kept piece is encoded again. Each is written as an MPEG-TS
piece, stamped with the time it will have in the finished film, and the pieces are joined end
to end. TS carries the H.264 parameter sets inside the stream, so the copied and the re-encoded
pieces (which differ in small encoder settings) can follow one another.

Sound: cut and muted in one pass and encoded once, alongside the picture. It cannot be copied,
because the mutes are part of it.

The picture and the sound keep the source's own offset between them, so lip sync is unchanged."""

import json
import shutil
import subprocess
import threading
import uuid
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path

from pydantic import BaseModel

from velvetdub.domain.export import EditPlan, Span
from velvetdub.domain.smartcut import (
    Piece,
    VideoTiming,
    audio_spans,
    frame_ranges,
    plan_pieces,
)

# Pieces that are encoded again look like their neighbours at this quality, and there are few.
ENCODE_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p"]
ENCODE_ARGS += ["-profile:v", "high", "-x264-params", "repeat-headers=1:open-gop=0"]
# Every timestamp is made this many seconds later while the pieces are made, then moved back in
# the final step. B-frames make a picture's decode time earlier than its display time, so a film
# that starts at 0 would need negative decode times, which a TS piece cannot hold: its muxer then
# shifts that one piece and leaves the others, and the timeline falls out of step.
TS_HEAD_START = 2.0
# Sound is the slower half, so it counts for more of the progress.
VIDEO_WEIGHT, AUDIO_WEIGHT = 1.0, 2.0


class SourceInfo(BaseModel):
    timing: VideoTiming
    keyframes: list[int]  # frame numbers where decoding can start
    has_audio: bool


def _rate(text: str) -> Fraction | None:
    try:
        value = Fraction(text)
    except (ValueError, ZeroDivisionError):
        return None
    return value if value > 0 else None


def probe_for_smart_cut(ffprobe: str, source: Path) -> SourceInfo | None:
    """What a smart cut needs to know about the film, or None if it cannot safely be done.

    It is done only for ordinary H.264 with a steady frame rate: what the copied and the
    re-encoded pieces would need to agree on is then well known. Anything else is rendered the
    slow way instead, which works for every format."""
    streams = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-of", "json", str(source)],
        check=True,
        capture_output=True,
        text=True,
    )
    found = json.loads(streams.stdout).get("streams", [])
    video = next((s for s in found if s.get("codec_type") == "video"), None)
    if video is None or video.get("codec_name") != "h264" or video.get("pix_fmt") != "yuv420p":
        return None
    if video.get("field_order", "progressive") not in ("progressive", "unknown"):
        return None
    real, average = _rate(video.get("r_frame_rate", "")), _rate(video.get("avg_frame_rate", ""))
    if real is None or average is None or abs(real - average) / real > Fraction(1, 1000):
        return None  # a variable frame rate has no frame grid to cut on

    scan = [ffprobe, "-v", "error", "-select_streams", "v:0"]
    scan += ["-show_entries", "packet=pts_time,flags", "-of", "csv=p=0", str(source)]
    packets = subprocess.run(
        scan,
        check=True,
        capture_output=True,
        text=True,
    )
    times: list[float] = []
    keys: list[float] = []
    for line in packets.stdout.splitlines():
        stamp, _, flags = line.partition(",")
        if not stamp or stamp == "N/A":
            continue
        times.append(float(stamp))
        if "K" in flags:
            keys.append(float(stamp))
    if not times or not keys:
        return None
    start, duration = min(times), float(1 / real)
    frames = len(times)
    indexes = sorted({round((k - start) / duration) for k in keys})
    return SourceInfo(
        timing=VideoTiming(start=start, frame_duration=duration, frame_count=frames),
        keyframes=[i for i in indexes if 0 <= i < frames],
        has_audio=any(s.get("codec_type") == "audio" for s in found),
    )


def _within(spans: list[Span]) -> str:
    return "+".join(f"between(t,{start:.6f},{end:.6f})" for start, end in spans)


def audio_filter_script(keep: list[Span], mute: list[Span], first_pts: float) -> str:
    """Silence the mutes on the film's own timeline, keep the same stretches as the picture, and
    stamp the result so it starts where the picture does.

    Each stretch is cut with `atrim`, which cuts at the exact sample. (`aselect` would pick whole
    audio frames of about 23 ms, so every cut would be that much off and the errors would add up
    over a film with many cuts, until the sound no longer lined up with the picture.)"""
    muted = f"volume=enable='{_within(mute)}':volume=0," if mute else ""
    finish = f"asetpts=PTS-STARTPTS+{first_pts:.6f}/TB[a]\n"
    if len(keep) == 1:
        start, end = keep[0]
        return f"[0:a:0]{muted}atrim=start={start:.6f}:end={end:.6f},{finish}"
    lines = [
        f"[0:a:0]{muted}asplit={len(keep)}" + "".join(f"[s{i}]" for i in range(len(keep))) + ";\n"
    ]
    for i, (start, end) in enumerate(keep):
        lines.append(f"[s{i}]atrim=start={start:.6f}:end={end:.6f},asetpts=PTS-STARTPTS[t{i}];\n")
    joined = "".join(f"[t{i}]" for i in range(len(keep)))
    lines.append(f"{joined}concat=n={len(keep)}:v=0:a=1,{finish}")
    return "".join(lines)


def _run(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, command, stderr=result.stderr)


class _Progress:
    """Picture and sound are made side by side; this folds them into one fraction."""

    def __init__(self, report: Callable[[float], None], with_audio: bool) -> None:
        self._report = report
        self._weights = (VIDEO_WEIGHT, AUDIO_WEIGHT if with_audio else 0.0)
        self._done = [0.0, 0.0]
        self._lock = threading.Lock()

    def update(self, which: int, fraction: float) -> None:
        with self._lock:
            self._done[which] = min(1.0, max(0.0, fraction))
            total = sum(self._weights)
            done = sum(w * f for w, f in zip(self._weights, self._done, strict=True))
            self._report(min(0.99, done / total))


class SmartCutRenderer:
    def __init__(self, ffmpeg: str, ffprobe: str) -> None:
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe

    def probe(self, source: Path) -> SourceInfo | None:
        return probe_for_smart_cut(self._ffprobe, source)

    def render(
        self,
        source: Path,
        dest: Path,
        plan: EditPlan,
        info: SourceInfo,
        on_progress: Callable[[float], None],
    ) -> None:
        timing = info.timing
        ranges = frame_ranges(plan.keep, timing)
        if not ranges:
            raise ValueError("Everything would be cut, so there is nothing left to save.")
        pieces = plan_pieces(ranges, info.keyframes, timing.frame_count)
        total_frames = sum(p.frames for p in pieces)

        dest.parent.mkdir(parents=True, exist_ok=True)
        # A copy is made one at a time, so any work folder already here was left by one that was
        # cut short (the server stopped); it can be gigabytes.
        for stale in dest.parent.glob("work-*"):
            shutil.rmtree(stale, ignore_errors=True)
        work = dest.parent / f"work-{uuid.uuid4().hex}"
        work.mkdir()
        partial = dest.with_name(f"{dest.stem}.partial{dest.suffix}")
        progress = _Progress(on_progress, info.has_audio)
        audio_error: list[BaseException] = []
        audio_process: list[subprocess.Popen[str]] = []
        audio_thread: threading.Thread | None = None
        try:
            if info.has_audio:
                audio_thread = threading.Thread(
                    target=self._audio_worker,
                    args=(source, work, plan, ranges, timing, progress, audio_error, audio_process),
                    name="export-audio",
                )
                audio_thread.start()
            video = work / "video.ts"
            self._render_video(source, video, pieces, timing, total_frames, work, progress)
            if audio_thread is not None:
                audio_thread.join()
                if audio_error:
                    raise audio_error[0]
            audio_file = work / "audio.m4a" if info.has_audio else None
            self._mux(video, audio_file, partial, timing, work)
            partial.replace(dest)
            on_progress(1.0)
        except BaseException:
            for process in audio_process:
                process.kill()
            partial.unlink(missing_ok=True)
            raise
        finally:
            if audio_thread is not None:
                audio_thread.join()
            shutil.rmtree(work, ignore_errors=True)

    def _render_video(
        self,
        source: Path,
        video: Path,
        pieces: list[Piece],
        timing: VideoTiming,
        total_frames: int,
        work: Path,
        progress: _Progress,
    ) -> None:
        done = 0
        with video.open("wb") as joined:
            for index, piece in enumerate(pieces):
                part = work / f"piece-{index:05d}.ts"
                _run(self._piece_command(source, part, piece, timing, done))
                with part.open("rb") as written:
                    shutil.copyfileobj(written, joined, 1024 * 1024)
                part.unlink()
                done += piece.frames
                progress.update(0, done / total_frames)

    def _piece_command(
        self, source: Path, part: Path, piece: Piece, timing: VideoTiming, out_first: int
    ) -> list[str]:
        """One TS piece, with its pictures stamped at the time they will have in the finished
        film (the film's own start offset included, so the sound still lines up)."""
        frame = timing.frame_duration
        command = [self._ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-copyts"]
        if piece.kind == "copy":
            # A copy starts at the last keyframe at or before the time asked for, found by decode
            # time. Half a frame after the keyframe's own time is after it whether or not the
            # film has B-frames (which make decode time earlier than display time) and well
            # before the next keyframe.
            seek = timing.time_of(piece.first_frame) + frame / 2
            codec = ["-c:v", "copy", "-bsf:v", "h264_mp4toannexb"]
        else:
            seek = timing.time_of(piece.first_frame) - frame / 2  # half a frame before: exact
            codec = ENCODE_ARGS
        shift = (out_first - piece.first_frame) * frame + TS_HEAD_START
        command += ["-ss", f"{max(0.0, seek):.6f}", "-i", str(source)]
        command += ["-frames:v", str(piece.frames), "-an", *codec]
        command += ["-output_ts_offset", f"{shift:.6f}", "-f", "mpegts", "-mpegts_copyts", "1"]
        command += ["-muxdelay", "0", "-muxpreload", "0", str(part)]
        return command

    def _audio_worker(
        self,
        source: Path,
        work: Path,
        plan: EditPlan,
        ranges: list[tuple[int, int]],
        timing: VideoTiming,
        progress: _Progress,
        errors: list[BaseException],
        processes: list[subprocess.Popen[str]],
    ) -> None:
        try:
            keep = audio_spans(ranges, timing)
            script = work / "audio.txt"
            first = timing.start + TS_HEAD_START
            script.write_text(audio_filter_script(keep, plan.mute, first), encoding="utf-8")
            command = [self._ffmpeg, "-y", "-loglevel", "error", "-nostats", "-progress", "pipe:1"]
            command += ["-i", str(source), "-filter_complex_script", str(script)]
            command += [
                "-map",
                "[a]",
                "-vn",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                str(work / "audio.m4a"),
            ]
            total = max(sum(end - start for start, end in keep), 0.001)
            process = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            processes.append(process)
            assert process.stdout is not None
            for line in process.stdout:
                key, _, value = line.strip().partition("=")
                if key == "out_time_us" and value.isdigit():
                    progress.update(1, int(value) / 1_000_000 / total)
            _, stderr = process.communicate()
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command, stderr=stderr)
            progress.update(1, 1.0)
        except BaseException as error:
            errors.append(error)

    def _mux(
        self, video: Path, audio: Path | None, dest: Path, timing: VideoTiming, work: Path
    ) -> None:
        """Put the picture and the sound in one MP4, with the picture's decode times redone.

        Each piece came with decode times of its own, and where a copied piece follows an encoded
        one they overlap (the copy's first picture is decoded two or three frames before it is
        shown, but those decode slots were already used). The muxer nudges them apart, which can
        leave a few frames at that join with the wrong place in the player's reorder window.
        With one picture per packet and a steady frame rate there is a simple valid answer for the
        whole stream: decode times one frame apart, in decode order, as late as they can be while
        none comes after its picture is shown."""
        stamped = work / "stamped.mp4"
        # Moves the head start back out of the picture. The sound is moved the same way below.
        back = [
            self._ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-copyts",
            "-i",
            str(video),
        ]
        back += ["-map", "0:v:0", "-c", "copy", "-output_ts_offset", f"{-TS_HEAD_START:.6f}"]
        _run([*back, str(stamped)])
        base = self._latest_decode_start(stamped, timing.frame_duration)
        step = timing.frame_duration
        command = [self._ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-copyts"]
        command += ["-i", str(stamped)]
        if audio is not None:
            command += ["-itsoffset", f"{-TS_HEAD_START:.6f}", "-i", str(audio)]
        command += ["-map", "0:v:0"] + (["-map", "1:a:0"] if audio is not None else [])
        # pts=PTS is needed: setts sets both times to the one expression unless told otherwise.
        stamps = f"setts=pts=PTS:dts=(N*{step:.9f}+({base:.9f}))/TB"
        command += ["-c", "copy", "-bsf:v", stamps]
        command += ["-movflags", "+faststart", str(dest)]
        _run(command)

    def _latest_decode_start(self, video: Path, frame: float) -> float:
        """The time the first packet can be decoded at, if each one after it is decoded a frame
        later: as late as possible without any picture being decoded after it is shown."""
        scan = [self._ffprobe, "-v", "error", "-select_streams", "v:0"]
        scan += ["-show_entries", "packet=pts_time", "-of", "csv=p=0", str(video)]
        listing = subprocess.run(
            scan,
            check=True,
            capture_output=True,
            text=True,
        )
        shown = [float(line.strip(",")) for line in listing.stdout.split()]
        return min(pts - index * frame for index, pts in enumerate(shown))
