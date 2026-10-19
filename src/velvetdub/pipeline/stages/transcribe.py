from pathlib import Path

from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.artifacts import write_model


class TranscribeStage(Stage):
    """Transcribes the film's dialogue, only when swearing is to be found or subtitles written.

    This is the step that costs transcription credits, so with neither chosen it does nothing."""

    name = "transcribe"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.original_audio] if ctx.options.needs_transcript else []

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.transcript] if ctx.options.needs_transcript else []

    def config_key(self, ctx: PipelineContext) -> str:
        if not ctx.options.needs_transcript:
            return "not-needed"
        return f"{ctx.providers.transcriber.identity}|{ctx.options.source_language}"

    def run(self, ctx: PipelineContext) -> None:
        if not ctx.options.needs_transcript:
            return
        transcript = ctx.providers.transcriber.transcribe(
            ctx.paths.original_audio, ctx.options.source_language
        )
        write_model(ctx.paths.transcript, transcript)
