"""Runs the pipeline in the background and tracks progress for the UI to poll."""

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum

from pydantic import BaseModel, Field

from velvetdub.domain.manifest import Manifest
from velvetdub.errors import StageFailedError
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.pipeline.observer import PipelineObserver


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class StageProgress(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


class JobState(BaseModel):
    title_id: str
    status: JobStatus = JobStatus.QUEUED
    stages: dict[str, StageProgress] = Field(default_factory=dict)
    error: str | None = None


Runner = Callable[[Manifest, ProcessOptions, PipelineObserver], None]


class _JobObserver(PipelineObserver):
    def __init__(self, state: JobState, lock: threading.Lock) -> None:
        self._state = state
        self._lock = lock

    def _set(self, stage: str, progress: StageProgress) -> None:
        with self._lock:
            self._state.stages[stage] = progress

    def stage_started(self, stage: str) -> None:
        self._set(stage, StageProgress.RUNNING)

    def stage_skipped(self, stage: str) -> None:
        self._set(stage, StageProgress.SKIPPED)

    def stage_finished(self, stage: str) -> None:
        self._set(stage, StageProgress.DONE)

    def stage_failed(self, stage: str, error: str) -> None:
        self._set(stage, StageProgress.FAILED)
        with self._lock:
            self._state.error = error


class JobManager:
    """One worker, so films are processed one at a time (the services are rate-limited and
    paid per use, and a laptop should not run two analyses at once). Progress lives in memory;
    the manifest on disk is the durable record of what finished."""

    def __init__(self, run: Runner, stage_names: list[str]) -> None:
        self._run = run
        self._stage_names = stage_names
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pipeline")
        self._jobs: dict[tuple[str, str], JobState] = {}
        self._lock = threading.Lock()

    def submit(self, manifest: Manifest, options: ProcessOptions) -> JobState:
        key = (manifest.owner_id, manifest.title_id)
        with self._lock:
            existing = self._jobs.get(key)
            if existing and existing.status in (JobStatus.QUEUED, JobStatus.RUNNING):
                return existing.model_copy(deep=True)
            state = JobState(
                title_id=manifest.title_id,
                stages={name: StageProgress.PENDING for name in self._stage_names},
            )
            self._jobs[key] = state
        self._executor.submit(self._work, state, manifest, options)
        return state.model_copy(deep=True)

    def get(self, owner_id: str, title_id: str) -> JobState | None:
        with self._lock:
            state = self._jobs.get((owner_id, title_id))
            return state.model_copy(deep=True) if state else None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _work(self, state: JobState, manifest: Manifest, options: ProcessOptions) -> None:
        with self._lock:
            state.status = JobStatus.RUNNING
        try:
            self._run(manifest, options, _JobObserver(state, self._lock))
        except StageFailedError:
            with self._lock:
                state.status = JobStatus.FAILED  # the observer already recorded why
        except Exception as exc:
            with self._lock:
                state.status = JobStatus.FAILED
                state.error = str(exc)
        else:
            with self._lock:
                state.status = JobStatus.DONE
