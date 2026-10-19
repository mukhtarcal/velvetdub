from pathlib import Path

from velvetdub.domain.transcript import Transcript
from velvetdub.features.translation.translator import Translator
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.pipeline.stages.dubbing import dub_targets
from velvetdub.storage.artifacts import read_model, write_model


class DubTranslateStage(Stage):
    """Writes the script for each dub language: lines to be spoken in the time the original took."""

    name = "dub_translate"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.dub_transcript] if ctx.options.dub_languages else []

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.dub_translation(lang) for lang in dub_targets(ctx)]

    def config_key(self, ctx: PipelineContext) -> str:
        if not ctx.options.dub_languages:
            return "no-dub"
        return f"{ctx.providers.text_generator.identity}|{','.join(ctx.options.dub_languages)}"

    def run(self, ctx: PipelineContext) -> None:
        targets = dub_targets(ctx)
        if not targets:
            return
        transcript = read_model(ctx.paths.dub_transcript, Transcript)
        translator = Translator(ctx.providers.text_generator)
        for language in targets:
            translation = translator.translate(transcript, language, for_dubbing=True)
            write_model(ctx.paths.dub_translation(language), translation)
