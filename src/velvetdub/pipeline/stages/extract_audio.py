from pathlib import Path

from velvetdub.domain.manifest import AudioTrack, TrackKind
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage


class ExtractAudioStage(Stage):
    name = "extract_audio"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.source]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.original_audio]

    def run(self, ctx: PipelineContext) -> None:
        ctx.media.extract_audio(ctx.paths.source, ctx.paths.original_audio)
        ctx.manifest.duration = ctx.media.probe_duration(ctx.paths.source)
        ctx.manifest.upsert_audio_track(
            AudioTrack(
                id="original",
                label="Original",
                language=None,
                kind=TrackKind.ORIGINAL,
                path=ctx.paths.relative(ctx.paths.original_audio),
            )
        )
