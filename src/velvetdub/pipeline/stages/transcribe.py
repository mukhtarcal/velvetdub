from pathlib import Path

from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.artifacts import write_model


class TranscribeStage(Stage):
    name = "transcribe"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.original_audio]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.transcript]

    def config_key(self, ctx: PipelineContext) -> str:
        return f"{ctx.providers.transcriber.identity}|{ctx.options.source_language}"

    def run(self, ctx: PipelineContext) -> None:
        transcript = ctx.providers.transcriber.transcribe(
            ctx.paths.original_audio, ctx.options.source_language
        )
        write_model(ctx.paths.transcript, transcript)
