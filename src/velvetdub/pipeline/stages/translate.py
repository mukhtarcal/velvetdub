from pathlib import Path

from velvetdub.domain.transcript import Transcript
from velvetdub.domain.translation import TranslatedSegment, Translation
from velvetdub.features.translation.translator import Translator
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.artifacts import read_model, write_model


class TranslateStage(Stage):
    """One translation file per subtitle language (dubs are translated by their own stage).

    A target equal to the spoken language is written as an identity translation, so downstream
    stages treat every language the same way.
    """

    name = "translate"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.transcript] if ctx.options.subtitle_languages else []

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.translation(lang) for lang in ctx.options.subtitle_languages]

    def config_key(self, ctx: PipelineContext) -> str:
        if not ctx.options.subtitle_languages:
            return "no-subtitles"
        languages = ",".join(ctx.options.subtitle_languages)
        return f"{ctx.providers.text_generator.identity}|{languages}"

    def run(self, ctx: PipelineContext) -> None:
        if not ctx.options.subtitle_languages:
            return
        transcript = read_model(ctx.paths.transcript, Transcript)
        translator = Translator(ctx.providers.text_generator)
        for language in ctx.options.subtitle_languages:
            if language == transcript.language:
                translation = Translation(
                    language=language,
                    segments=[
                        TranslatedSegment(segment_id=s.id, text=s.text, target_duration=s.duration)
                        for s in transcript.segments
                    ],
                )
            else:
                translation = translator.translate(transcript, language)
            write_model(ctx.paths.translation(language), translation)
