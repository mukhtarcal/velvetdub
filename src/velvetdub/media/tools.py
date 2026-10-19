"""Media tooling behind an interface, so tests can run without ffmpeg."""

import math
import shutil
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from velvetdub.domain.dubbing import LINE_SAMPLE_RATE, Placement
from velvetdub.domain.export import EditPlan, Span
from velvetdub.errors import ToolNotFoundError
from velvetdub.media.dialogue import assemble_dialogue
from velvetdub.media.smartcut import SmartCutRenderer


class ScanClip(BaseModel):
    """A short, low-resolution piece of the film for visual moderation.

    `offset` is where the clip starts in the full film, in seconds, so detections found inside
    the clip can be placed on the film's own timeline.
    """

    model_config = ConfigDict(frozen=True)

    path: Path
    offset: float
    duration: float


class MediaTool(ABC):
    @abstractmethod
    def extract_audio(self, source: Path, dest: Path) -> None:
        """Write the source's audio track to `dest`."""

    @abstractmethod
    def probe_duration(self, source: Path) -> float:
        """Length in seconds."""

    @abstractmethod
    def make_scan_clips(
        self,
        source: Path,
        out_dir: Path,
        *,
        clip_seconds: int,
        fps: float,
        height: int,
        crf: int = 30,
    ) -> list[ScanClip]:
        """Cut the video into small, silent, low-resolution clips for visual analysis.
        `crf` is the video quality (lower is sharper)."""

    @abstractmethod
    def extract_frames(self, clip: Path, out_dir: Path) -> list[Path]:
        """Write every frame of `clip` as a JPEG, in order, and return their paths."""

    @abstractmethod
    def render_cleaned(
        self, source: Path, dest: Path, plan: EditPlan, on_progress: Callable[[float], None]
    ) -> None:
        """Write a copy of `source` at `dest` with the plan applied: only the parts to keep, and
        the sound silenced where the plan says. `on_progress` gets the fraction done (0 to 1)."""

    @abstractmethod
    def extract_poster(self, source: Path, dest: Path, *, at_seconds: float) -> None:
        """Write one representative picture from near `at_seconds` as a JPEG at `dest`."""

    @abstractmethod
    def extract_mix(self, source: Path, dest: Path) -> None:
        """Write the source's sound as a 44.1 kHz stereo 16-bit WAV, for separating voices."""

    @abstractmethod
    def cut_audio(self, source: Path, spans: Sequence[Span], dest: Path) -> None:
        """Write the given spans of `source`'s sound, joined in order, as one mono WAV."""

    @abstractmethod
    def change_tempo(self, source: Path, dest: Path, factor: float) -> None:
        """Write a spoken line (a line WAV) played `factor` times faster, without changing pitch.
        The result is in the same format as the input."""

    @abstractmethod
    def mix_dub(self, lines: Sequence[Placement], background: Path, dest: Path) -> None:
        """Put the spoken lines at their start times over the background sound, even out the
        loudness, and write the result as an AAC file at `dest`."""


POSTER_WIDTH = 640
# ffmpeg's `thumbnail` filter picks the most typical frame out of this many, which skips the
# black or half-faded frames that a single frame at an exact time often lands on.
POSTER_CANDIDATES = 100


def _within(spans: Iterable[Span]) -> str:
    """An ffmpeg expression that is true at any moment inside one of the spans."""
    return "+".join(f"between(t,{start:.3f},{end:.3f})" for start, end in spans)


def cleaned_filter_script(plan: EditPlan) -> str:
    """The ffmpeg filter graph for a plan. Sound is silenced first, on the film's own timeline,
    and then both picture and sound keep only the same pieces, so they stay in step."""
    audio = ["[0:a]"]
    if plan.mute:
        audio.append(f"volume=enable='{_within(plan.mute)}':volume=0,")
    video = ["[0:v]"]
    whole = plan.keep == [(0.0, plan.source_duration)]
    if whole:
        video.append("null")
        audio.append("anull")
    else:
        video.append(f"select='{_within(plan.keep)}',setpts=N/FRAME_RATE/TB")
        audio.append(f"aselect='{_within(plan.keep)}',asetpts=N/SR/TB")
    return "".join(video) + "[v];\n" + "".join(audio) + "[a]\n"


class FFmpegMediaTool(MediaTool):
    def __init__(self) -> None:
        self._ffmpeg = self._require("ffmpeg")
        self._ffprobe = self._require("ffprobe")
        self._smart = SmartCutRenderer(self._ffmpeg, self._ffprobe)

    @staticmethod
    def _require(binary: str) -> str:
        path = shutil.which(binary)
        if path is None:
            raise ToolNotFoundError(f"'{binary}' was not found on PATH. Install ffmpeg first.")
        return path

    def extract_audio(self, source: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Mono 16 kHz AAC: small, and what speech models want.
        command = [self._ffmpeg, "-y", "-i", str(source), "-vn", "-ac", "1", "-ar", "16000"]
        command += ["-c:a", "aac", str(dest)]
        subprocess.run(command, check=True, capture_output=True)

    def probe_duration(self, source: Path) -> float:
        command = [self._ffprobe, "-v", "error", "-show_entries", "format=duration"]
        command += ["-of", "default=noprint_wrappers=1:nokey=1", str(source)]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return float(result.stdout.strip())

    def make_scan_clips(
        self,
        source: Path,
        out_dir: Path,
        *,
        clip_seconds: int,
        fps: float,
        height: int,
        crf: int = 30,
    ) -> list[ScanClip]:
        out_dir.mkdir(parents=True, exist_ok=True)
        total = self.probe_duration(source)
        clips: list[ScanClip] = []
        for index in range(max(1, math.ceil(total / clip_seconds))):
            offset = float(index * clip_seconds)
            duration = min(float(clip_seconds), total - offset)
            if duration <= 0:
                break
            path = out_dir / f"clip_{index:04d}.mp4"
            command = [self._ffmpeg, "-y", "-ss", str(offset), "-t", str(duration)]
            command += ["-i", str(source), "-an"]
            command += ["-vf", f"fps={fps},scale=-2:{height}"]
            command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf), str(path)]
            subprocess.run(command, check=True, capture_output=True)
            clips.append(ScanClip(path=path, offset=offset, duration=duration))
        return clips

    def extract_frames(self, clip: Path, out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        command = [self._ffmpeg, "-y", "-i", str(clip), "-q:v", "3", str(out_dir / "f_%05d.jpg")]
        subprocess.run(command, check=True, capture_output=True)
        return sorted(out_dir.glob("f_*.jpg"))

    def extract_poster(self, source: Path, dest: Path, *, at_seconds: float) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        command = [self._ffmpeg, "-y", "-ss", f"{max(0.0, at_seconds):.2f}", "-i", str(source)]
        command += ["-vf", f"thumbnail={POSTER_CANDIDATES},scale={POSTER_WIDTH}:-2"]
        command += ["-frames:v", "1", "-q:v", "3", str(dest)]
        subprocess.run(command, check=True, capture_output=True)

    def extract_mix(self, source: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        command = [self._ffmpeg, "-y", "-i", str(source), "-vn", "-ac", "2", "-ar", "44100"]
        command += ["-c:a", "pcm_s16le", str(dest)]
        subprocess.run(command, check=True, capture_output=True)

    def cut_audio(self, source: Path, spans: Sequence[Span], dest: Path) -> None:
        if not spans:
            raise ValueError("There is nothing to cut.")
        dest.parent.mkdir(parents=True, exist_ok=True)
        pieces = [
            f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{i}];"
            for i, (start, end) in enumerate(spans)
        ]
        joined = "".join(f"[a{i}]" for i in range(len(spans)))
        graph = "".join(pieces) + f"{joined}concat=n={len(spans)}:v=0:a=1[out]"
        command = [self._ffmpeg, "-y", "-i", str(source), "-filter_complex", graph]
        command += ["-map", "[out]", "-ac", "1", "-c:a", "pcm_s16le", str(dest)]
        subprocess.run(command, check=True, capture_output=True)

    def change_tempo(self, source: Path, dest: Path, factor: float) -> None:
        command = [self._ffmpeg, "-y", "-i", str(source), "-filter:a", f"atempo={factor:.4f}"]
        command += ["-ar", str(LINE_SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dest)]
        subprocess.run(command, check=True, capture_output=True)

    def mix_dub(self, lines: Sequence[Placement], background: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dialogue = dest.with_name(f"{dest.stem}.dialogue.wav")
        partial = dest.with_name(f"{dest.stem}.partial{dest.suffix}")
        try:
            assemble_dialogue(lines, dialogue)
            graph = "[1:a]aresample=44100[d];[0:a][d]amix=inputs=2:normalize=0:duration=first,"
            graph += "loudnorm=I=-16:TP=-1.5:LRA=11"
            command = [self._ffmpeg, "-y", "-i", str(background), "-i", str(dialogue)]
            command += ["-filter_complex", graph, "-c:a", "aac", "-b:a", "160k", str(partial)]
            subprocess.run(command, check=True, capture_output=True)
            partial.replace(dest)
        finally:
            dialogue.unlink(missing_ok=True)
            partial.unlink(missing_ok=True)

    def render_cleaned(
        self, source: Path, dest: Path, plan: EditPlan, on_progress: Callable[[float], None]
    ) -> None:
        if not plan.keep:
            raise ValueError("Everything would be cut, so there is nothing left to save.")
        # Copying most of the picture is many times faster than encoding all of it, and it is
        # what a film in an ordinary format gets. Anything else is encoded the slow way.
        info = self._smart.probe(source)
        if info is not None:
            self._smart.render(source, dest, plan, info, on_progress)
        else:
            self._render_full(source, dest, plan, on_progress)

    def _render_full(
        self, source: Path, dest: Path, plan: EditPlan, on_progress: Callable[[float], None]
    ) -> None:
        """Every frame is decoded and encoded again. Slow, but works for any format."""
        dest.parent.mkdir(parents=True, exist_ok=True)
        # The graph is long when there are many cuts, so it goes in a file, not on the command line.
        script = dest.with_name(f"{dest.stem}.filters.txt")
        partial = dest.with_name(f"{dest.stem}.partial{dest.suffix}")
        script.write_text(cleaned_filter_script(plan), encoding="utf-8")
        command = [self._ffmpeg, "-y", "-loglevel", "error", "-nostats", "-progress", "pipe:1"]
        command += ["-i", str(source), "-filter_complex_script", str(script)]
        command += ["-map", "[v]", "-map", "[a]"]
        command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
        command += ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(partial)]
        total = max(plan.output_duration, 0.001)
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        try:
            assert process.stdout is not None
            for line in process.stdout:
                key, _, value = line.strip().partition("=")
                if key == "out_time_us" and value.isdigit():
                    on_progress(min(1.0, int(value) / 1_000_000 / total))
            _, errors = process.communicate()
        except BaseException:
            process.kill()
            partial.unlink(missing_ok=True)
            raise
        finally:
            script.unlink(missing_ok=True)
        if process.returncode != 0:
            partial.unlink(missing_ok=True)
            raise subprocess.CalledProcessError(process.returncode, command, stderr=errors)
        partial.replace(dest)
        on_progress(1.0)
