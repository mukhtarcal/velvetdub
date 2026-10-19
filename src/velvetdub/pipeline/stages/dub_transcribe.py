from pathlib import Path

from velvetdub.features.dubbing.sentences import merge_sentences
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.artifacts import write_model


class DubTranscribeStage(Stage):
    """Listens to the separated dialogue and writes what was said, in whole sentences.

    The dialogue alone is transcribed (not the original mix) because music under speech
    smears the word timings, and a dub is placed by those timings."""

    name = "dub_transcribe"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.dub_dialogue] if ctx.options.dub_languages else []

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.dub_transcript] if ctx.options.dub_languages else []

    def config_key(self, ctx: PipelineContext) -> str:
        if not ctx.options.dub_languages:
            return "no-dub"
        return f"{ctx.providers.transcriber.identity}|{ctx.options.source_language}"

    def run(self, ctx: PipelineContext) -> None:
        if not ctx.options.dub_languages:
            return
        ctx.media.extract_audio(ctx.paths.dub_dialogue, ctx.paths.dub_speech)
        transcript = ctx.providers.transcriber.transcribe(
            ctx.paths.dub_speech, ctx.options.source_language
        )
        write_model(ctx.paths.dub_transcript, merge_sentences(transcript))
