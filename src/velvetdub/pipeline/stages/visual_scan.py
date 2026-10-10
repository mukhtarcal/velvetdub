import tempfile
from pathlib import Path

from velvetdub.domain.filtering import FilterEvent, FilterTimeline
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.artifacts import write_model


class VisualScanStage(Stage):
    """Cuts the film into small clips and asks the moderator about each one."""

    name = "visual_scan"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.source]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.visual_events]

    def config_key(self, ctx: PipelineContext) -> str:
        s = ctx.settings
        return (
            f"{ctx.providers.moderator.identity}|fps={s.visual_sample_fps}"
            f"|clip={s.scan_clip_seconds}|h={s.scan_height}"
        )

    def run(self, ctx: PipelineContext) -> None:
        settings = ctx.settings
        events: list[FilterEvent] = []
        # Clips are temporary (many GB for a long film if kept), so they live in a temp dir
        with tempfile.TemporaryDirectory(prefix="vd-scan-") as scratch:
            clips = ctx.media.make_scan_clips(
                ctx.paths.source,
                Path(scratch),
                clip_seconds=settings.scan_clip_seconds,
                fps=settings.visual_sample_fps,
                height=settings.scan_height,
            )
            for clip in clips:
                events.extend(ctx.providers.moderator.scan_clip(clip.path, offset=clip.offset))
        write_model(ctx.paths.visual_events, FilterTimeline(events=events))
