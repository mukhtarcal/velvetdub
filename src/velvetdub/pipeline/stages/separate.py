from pathlib import Path

from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage


class SeparateStage(Stage):
    """Splits the film's sound into dialogue and everything else (music, effects). The dub
    replaces the dialogue and keeps the rest. Does nothing unless a dub was asked for."""

    name = "separate"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.source] if ctx.options.dub_languages else []

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        if not ctx.options.dub_languages:
            return []
        return [ctx.paths.dub_dialogue, ctx.paths.dub_background]

    def config_key(self, ctx: PipelineContext) -> str:
        return ctx.providers.separator.identity if ctx.options.dub_languages else "no-dub"

    def run(self, ctx: PipelineContext) -> None:
        if not ctx.options.dub_languages:
            return
        ctx.media.extract_mix(ctx.paths.source, ctx.paths.dub_mix)
        try:
            ctx.providers.separator.separate(ctx.paths.dub_mix, ctx.paths.dub_stems)
        finally:
            ctx.paths.dub_mix.unlink(missing_ok=True)  # the whole sound is large; the stems stay
