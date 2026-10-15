"""Makes a cleaned copy of a film: the cuts you settled on (scenes removed, words muted) applied
for good, so it can be watched anywhere. The original is never changed.

A full film takes a while, so the copy is made in the background and the page polls for progress.
The copy is remembered against the exact cuts it was made from: asking again with nothing changed
hands back the saved copy, and changing a cut makes the saved copy out of date."""

import re
import threading
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from velvetdub.domain.export import EditPlan, plan_edit
from velvetdub.media.tools import MediaTool
from velvetdub.services.playback import PlaybackService
from velvetdub.storage.artifacts import read_model, write_model
from velvetdub.storage.title_store import TitleStore


class ExportStatus(StrEnum):
    NONE = "none"  # nothing made yet, or the saved copy no longer matches the cuts
    WORKING = "working"
    READY = "ready"  # a copy that matches the cuts exactly
    FAILED = "failed"


class ExportState(BaseModel):
    status: ExportStatus
    percent: int = 0
    error: str | None = None
    filename: str
    size_bytes: int | None = None
    # What the copy made from the cuts as they are now will be like.
    output_seconds: float
    removed_seconds: float
    cuts: int
    muted_words: int


class _Record(BaseModel):
    fingerprint: str


class _Job:
    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint
        self.percent = 0.0  # fraction done, 0 to 1
        self.error: str | None = None
        self.done = False


_UNSAFE = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def download_name(title: str) -> str:
    cleaned = _UNSAFE.sub(" ", title).strip(" .") or "film"
    return f"{' '.join(cleaned.split())} (cleaned).mp4"


class ExportService:
    """One copy is made at a time: it uses every core, and a laptop has only so many to give."""

    def __init__(self, store: TitleStore, playback: PlaybackService, media: MediaTool) -> None:
        self._store = store
        self._playback = playback
        self._media = media
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="export")
        self._jobs: dict[tuple[str, str], _Job] = {}
        self._lock = threading.Lock()

    def _plan(self, owner_id: str, title_id: str) -> tuple[EditPlan, str]:
        manifest = self._store.get(owner_id, title_id)
        paths = self._store.paths(manifest)
        duration = manifest.duration or self._media.probe_duration(paths.source)
        filters = self._playback.resolved_filters(owner_id, title_id)
        return plan_edit(filters, duration), manifest.name

    def state(self, owner_id: str, title_id: str) -> ExportState:
        plan, name = self._plan(owner_id, title_id)
        paths = self._store.paths(self._store.get(owner_id, title_id))
        summary = {
            "filename": download_name(name),
            "output_seconds": plan.output_duration,
            "removed_seconds": plan.removed,
            "cuts": plan.cuts,
            "muted_words": len(plan.mute),
        }
        with self._lock:
            job = self._jobs.get((owner_id, title_id))
            if job and not job.done:
                return ExportState(
                    status=ExportStatus.WORKING, percent=int(job.percent * 100), **summary
                )
            if job and job.error and job.fingerprint == plan.fingerprint():
                return ExportState(status=ExportStatus.FAILED, error=job.error, **summary)
        if self._saved_matches(paths.export_video, paths.export_record, plan):
            return ExportState(
                status=ExportStatus.READY,
                percent=100,
                size_bytes=paths.export_video.stat().st_size,
                **summary,
            )
        return ExportState(status=ExportStatus.NONE, **summary)

    @staticmethod
    def _saved_matches(video: Path, record: Path, plan: EditPlan) -> bool:
        if not video.is_file() or not record.is_file():
            return False
        return read_model(record, _Record).fingerprint == plan.fingerprint()

    def start(self, owner_id: str, title_id: str) -> ExportState:
        """Begin making the copy, unless one is under way or the saved copy is already right."""
        current = self.state(owner_id, title_id)
        if current.status in (ExportStatus.WORKING, ExportStatus.READY):
            return current
        plan, _ = self._plan(owner_id, title_id)
        manifest = self._store.get(owner_id, title_id)
        job = _Job(plan.fingerprint())
        with self._lock:
            self._jobs[(owner_id, title_id)] = job
        self._executor.submit(self._work, job, manifest.title_id, owner_id, plan)
        return self.state(owner_id, title_id)

    def file(self, owner_id: str, title_id: str) -> tuple[Path, str] | None:
        """The finished copy and the name to save it under, or None if it is not ready."""
        state = self.state(owner_id, title_id)
        if state.status is not ExportStatus.READY:
            return None
        paths = self._store.paths(self._store.get(owner_id, title_id))
        return paths.export_video, state.filename

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _work(self, job: _Job, title_id: str, owner_id: str, plan: EditPlan) -> None:
        try:
            paths = self._store.paths(self._store.get(owner_id, title_id))

            def progress(fraction: float) -> None:
                job.percent = fraction

            self._media.render_cleaned(paths.source, paths.export_video, plan, progress)
            write_model(paths.export_record, _Record(fingerprint=job.fingerprint))
        except Exception as error:
            job.error = _plain(error)
        finally:
            job.done = True


def _plain(error: Exception) -> str:
    """A short reason for the page, without a wall of ffmpeg output."""
    detail = getattr(error, "stderr", None)
    if isinstance(detail, str) and detail.strip():
        return "The copy could not be made: " + detail.strip().splitlines()[-1][:300]
    return f"The copy could not be made: {error}"
