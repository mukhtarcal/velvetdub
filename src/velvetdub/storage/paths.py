"""Where a title's files live. The only place that knows the folder layout."""

import re
from pathlib import Path

from velvetdub.errors import InvalidNameError

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")


def safe_name(value: str) -> str:
    """Language codes and track ids end up in file names, so only plain names are allowed."""
    if not _SAFE_NAME.fullmatch(value):
        raise InvalidNameError(f"Not a valid name: {value!r}")
    return value


class TitlePaths:
    def __init__(self, root: Path, source_filename: str) -> None:
        self.root = root
        self._source_filename = source_filename

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def source(self) -> Path:
        return self.root / self._source_filename

    @property
    def original_audio(self) -> Path:
        return self.root / "audio" / "original.m4a"

    def audio_track(self, track_id: str) -> Path:
        """Phase 2 dubs: audio/<track_id>.m4a"""
        return self.root / "audio" / f"{safe_name(track_id)}.m4a"

    @property
    def transcript(self) -> Path:
        return self.root / "transcript.json"

    def translation(self, language: str) -> Path:
        return self.root / "translations" / f"{safe_name(language)}.json"

    @property
    def visual_events(self) -> Path:
        return self.root / "scan" / "visual.json"

    @property
    def filters(self) -> Path:
        return self.root / "filters.json"

    @property
    def overrides(self) -> Path:
        return self.root / "overrides.json"

    def subtitles(self, language: str) -> Path:
        return self.root / "subtitles" / f"{safe_name(language)}.vtt"

    def relative(self, path: Path) -> str:
        """Path as stored in the manifest (relative to the title folder)."""
        return path.relative_to(self.root).as_posix()
