"""Runs stages in order, skipping any that are up to date, and records the results."""

from collections.abc import Sequence
from datetime import UTC, datetime

from velvetdub.domain.manifest import StageRecord, StageStatus
from velvetdub.errors import StageFailedError
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.title_store import TitleStore


class PipelineRunner:
    def __init__(self, stages: Sequence[Stage], store: TitleStore) -> None:
        self._stages = list(stages)
        self._store = store

    def run(self, ctx: PipelineContext) -> None:
        for stage in self._stages:
            # Computing the fingerprint can itself fail (missing input, missing API key),
            # so it lives inside the same error handling as the stage's own work.
            try:
                fingerprint = stage.fingerprint(ctx)
                record = ctx.manifest.stages.get(stage.name)
                if (
                    record is not None
                    and record.status is StageStatus.DONE
                    and record.fingerprint == fingerprint
                    and stage.outputs_exist(ctx)
                ):
                    ctx.observer.stage_skipped(stage.name)
                    continue

                ctx.observer.stage_started(stage.name)
                stage.run(ctx)
            except Exception as exc:
                self._record_failure(ctx, stage, exc)
                raise StageFailedError(stage.name) from exc

            ctx.manifest.stages[stage.name] = StageRecord(
                status=StageStatus.DONE,
                fingerprint=fingerprint,
                finished_at=datetime.now(UTC),
            )
            self._store.save(ctx.manifest)
            ctx.observer.stage_finished(stage.name)

    def _record_failure(self, ctx: PipelineContext, stage: Stage, exc: Exception) -> None:
        ctx.manifest.stages[stage.name] = StageRecord(status=StageStatus.FAILED, error=str(exc))
        self._store.save(ctx.manifest)
        ctx.observer.stage_failed(stage.name, str(exc))
