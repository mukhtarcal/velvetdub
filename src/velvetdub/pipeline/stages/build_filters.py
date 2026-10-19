from pathlib import Path

from velvetdub.domain.filtering import FilterTimeline
from velvetdub.domain.transcript import Transcript
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.artifacts import read_model, write_model


class BuildFiltersStage(Stage):
    """Merge what was found in the picture and, if swearing was chosen, in the words into one
    viewer-independent timeline. Always written, so a title with nothing chosen has an empty one."""

    name = "build_filters"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        spoken = [ctx.paths.transcript] if ctx.options.finds_swearing else []
        return [*spoken, ctx.paths.visual_events]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.filters]

    def config_key(self, ctx: PipelineContext) -> str:
        if not ctx.options.finds_swearing:
            return "no-swearing"
        return ctx.providers.text_moderator.identity

    def run(self, ctx: PipelineContext) -> None:
        visual = read_model(ctx.paths.visual_events, FilterTimeline)
        spoken = []
        if ctx.options.finds_swearing:
            transcript = read_model(ctx.paths.transcript, Transcript)
            spoken = ctx.providers.text_moderator.scan_transcript(transcript)
        ctx.manifest.swearing_checked = ctx.options.finds_swearing
        timeline = FilterTimeline(events=[*visual.events, *spoken])
        write_model(ctx.paths.filters, FilterTimeline(events=timeline.sorted_events()))
        # The library picture was chosen to avoid the old scenes, so choose it again.
        ctx.paths.poster.unlink(missing_ok=True)
