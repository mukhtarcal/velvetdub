from pathlib import Path

from velvetdub.domain.dubbing import DubLines, Placement
from velvetdub.domain.languages import language_name
from velvetdub.domain.manifest import AudioTrack, TrackKind
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.pipeline.stages.dubbing import dub_targets
from velvetdub.storage.artifacts import read_model


def dub_track_id(language: str) -> str:
    return f"dub-{language}"


class DubMixStage(Stage):
    """Lays the spoken lines over the film's music and effects and saves each dub as an audio
    track the player can switch to."""

    name = "dub_mix"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        targets = dub_targets(ctx)
        if not targets:
            return []
        return [ctx.paths.dub_background, *(ctx.paths.dub_lines(lang) for lang in targets)]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.audio_track(dub_track_id(lang)) for lang in dub_targets(ctx)]

    def config_key(self, ctx: PipelineContext) -> str:
        return ",".join(dub_targets(ctx)) or "no-dub"

    def run(self, ctx: PipelineContext) -> None:
        for language in dub_targets(ctx):
            lines = read_model(ctx.paths.dub_lines(language), DubLines)
            placements = [
                Placement(path=ctx.paths.root / line.path, start=line.start) for line in lines.lines
            ]
            dest = ctx.paths.audio_track(dub_track_id(language))
            ctx.media.mix_dub(placements, ctx.paths.dub_background, dest)
            ctx.manifest.upsert_audio_track(
                AudioTrack(
                    id=dub_track_id(language),
                    label=f"{language_name(language)} dub",
                    language=language,
                    kind=TrackKind.DUB,
                    path=ctx.paths.relative(dest),
                )
            )
