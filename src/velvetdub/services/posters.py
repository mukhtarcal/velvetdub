"""The picture shown for a title in the library, taken from the film itself.

The library is the one place a frame from the film is shown without anyone having chosen to
watch it, and the whole point of this tool is skipping some scenes. So a poster is only made once
the scan has run, and from a moment well clear of every scene it found.
"""

import subprocess
import uuid
from pathlib import Path

from velvetdub.domain.filtering import WORD_CATEGORIES, FilterEvent, FilterTimeline
from velvetdub.media.tools import MediaTool
from velvetdub.storage.artifacts import read_model
from velvetdub.storage.title_store import TitleStore

# Candidate moments, as fractions of the film: past the studio logos and opening black first.
CANDIDATES = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)
# How far a candidate must be from any found scene. A scene can really start a second before the
# scan says (see PICTURE_LEAD_SECONDS), and the frame is picked from the few seconds after the
# chosen time, so this keeps a good margin on both sides.
CLEARANCE_SECONDS = 10.0


def poster_time(duration: float, scenes: list[FilterEvent]) -> float | None:
    """The first candidate moment clear of every scene, or None if there is none."""
    for fraction in CANDIDATES:
        at = duration * fraction
        if all(
            at + CLEARANCE_SECONDS < scene.start or at - CLEARANCE_SECONDS > scene.end
            for scene in scenes
        ):
            return at
    return None


class PosterService:
    def __init__(self, store: TitleStore, media: MediaTool) -> None:
        self._store = store
        self._media = media

    def get(self, owner_id: str, title_id: str) -> Path | None:
        """The poster file, made on first use and kept. None when no safe picture exists yet."""
        manifest = self._store.get(owner_id, title_id)
        paths = self._store.paths(manifest)
        if not paths.filters.is_file() or not paths.source.is_file():
            return None  # not scanned yet, so there is no telling what a frame would show
        if paths.poster.is_file():
            return paths.poster

        timeline = read_model(paths.filters, FilterTimeline)
        scenes = [e for e in timeline.events if e.category not in WORD_CATEGORIES]
        duration = manifest.duration or self._media.probe_duration(paths.source)
        at = poster_time(duration, scenes)
        if at is None:
            return None

        # Written under another name and renamed, so a request that arrives while this one is
        # still working never serves half a picture.
        partial = paths.poster.with_name(f"poster.{uuid.uuid4().hex}.tmp.jpg")
        return self._make(paths.source, partial, paths.poster, at)

    def _make(self, source: Path, partial: Path, dest: Path, at: float) -> Path | None:
        try:
            self._media.extract_poster(source, partial, at_seconds=at)
            partial.replace(dest)
        except (subprocess.CalledProcessError, OSError):
            partial.unlink(missing_ok=True)
            return None
        return dest
