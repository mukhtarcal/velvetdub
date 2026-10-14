from pathlib import Path

from velvetdub.domain.filtering import FilterTimeline
from velvetdub.domain.transcript import Transcript
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.artifacts import read_model, write_model


class BuildFiltersStage(Stage):
    """Merge visual and spoken-word detections into one viewer-independent timeline."""

    name = "build_filters"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.transcript, ctx.paths.visual_events]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.filters]

    def config_key(self, ctx: PipelineContext) -> str:
        return ctx.providers.text_moderator.identity

    def run(self, ctx: PipelineContext) -> None:
        transcript = read_model(ctx.paths.transcript, Transcript)
        visual = read_model(ctx.paths.visual_events, FilterTimeline)
        spoken = ctx.providers.text_moderator.scan_transcript(transcript)
        timeline = FilterTimeline(events=[*visual.events, *spoken])
        write_model(ctx.paths.filters, FilterTimeline(events=timeline.sorted_events()))
        # The library picture was chosen to avoid the old scenes, so choose it again.
        ctx.paths.poster.unlink(missing_ok=True)
