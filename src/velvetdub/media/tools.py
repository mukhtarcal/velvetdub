"""Media tooling behind an interface, so tests can run without ffmpeg."""

import math
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from velvetdub.errors import ToolNotFoundError


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


class FFmpegMediaTool(MediaTool):
    def __init__(self) -> None:
        self._ffmpeg = self._require("ffmpeg")
        self._ffprobe = self._require("ffprobe")

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
