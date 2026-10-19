import hashlib
import shutil
import tempfile
from pathlib import Path

from pydantic import BaseModel

from velvetdub.domain.filtering import FilterTimeline
from velvetdub.domain.usage import TokenUsage
from velvetdub.features.scene_filtering.factory import build_scene_scanner
from velvetdub.features.scene_filtering.scanner import ClipScan
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.artifacts import read_model, write_model


class ScanUsage(BaseModel):
    """What the whole scan cost in tokens, for judging quota needs on long films."""

    clips: int
    input_tokens: int
    output_tokens: int


class VisualScanStage(Stage):
    """Cuts the film into small clips and has the scene scanner look at each one.

    Each clip's result is saved when it finishes, so a failure part way (a dropped connection,
    a used-up quota) resumes at the failed clip instead of paying for the whole film again.

    Only the categories you chose are looked for. With none chosen nothing is scanned: the stage
    writes an empty list and no scanner (or API key) is touched."""

    name = "visual_scan"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.source]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.visual_events]

    def config_key(self, ctx: PipelineContext) -> str:
        categories = ctx.options.picture_categories
        if not categories:
            return "no-categories"
        return build_scene_scanner(ctx.providers, ctx.settings, categories).config_key(ctx.settings)

    def run(self, ctx: PipelineContext) -> None:
        categories = ctx.options.picture_categories
        ctx.manifest.scanned_categories = categories
        if not categories:
            write_model(ctx.paths.visual_events, FilterTimeline())
            return
        settings = ctx.settings
        scanner = build_scene_scanner(ctx.providers, settings, categories)
        spec = scanner.clip_spec(settings)
        # Saved clips only count if the settings that made them are unchanged
        part_key = hashlib.sha256(self.config_key(ctx).encode()).hexdigest()[:16]
        results: list[ClipScan] = []
        # Clips are temporary (many GB for a long film if kept), so they live in a temp dir
        with tempfile.TemporaryDirectory(prefix="vd-scan-") as scratch:
            clips = ctx.media.make_scan_clips(
                ctx.paths.source,
                Path(scratch),
                clip_seconds=spec.seconds,
                fps=spec.fps,
                height=spec.height,
                crf=spec.crf,
            )
            for index, clip in enumerate(clips):
                part = ctx.paths.visual_part(part_key, index)
                if part.exists():
                    results.append(read_model(part, ClipScan))
                    continue
                scan = scanner.scan_clip(clip.path, offset=clip.offset, media=ctx.media)
                write_model(part, scan)
                results.append(scan)

        total = sum((r.usage for r in results), TokenUsage())
        write_model(
            ctx.paths.visual_usage,
            ScanUsage(
                clips=len(results),
                input_tokens=total.input_tokens,
                output_tokens=total.output_tokens,
            ),
        )
        events = [event for r in results for event in r.events]
        write_model(ctx.paths.visual_events, FilterTimeline(events=events))
        shutil.rmtree(ctx.paths.visual_part(part_key, 0).parent, ignore_errors=True)
