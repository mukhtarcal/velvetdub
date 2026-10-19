"""Shared by the dubbing stages."""

from velvetdub.domain.transcript import Transcript
from velvetdub.pipeline.context import PipelineContext
from velvetdub.storage.artifacts import read_model


def dub_targets(ctx: PipelineContext) -> list[str]:
    """The languages to dub into. A film is never dubbed into the language it is already in, and
    that is only known once the dialogue has been transcribed."""
    languages = ctx.options.dub_languages
    if not languages or not ctx.paths.dub_transcript.exists():
        return list(languages)
    spoken = read_model(ctx.paths.dub_transcript, Transcript).language
    return [language for language in languages if language != spoken]
