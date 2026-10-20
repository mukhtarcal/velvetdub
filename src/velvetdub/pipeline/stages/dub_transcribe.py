from pathlib import Path

from velvetdub.domain.dubbing import HeardTranscript
from velvetdub.features.dubbing.sentences import RULES_VERSION, merge_sentences
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.artifacts import read_model, write_model


class DubTranscribeStage(Stage):
    """Listens to the separated dialogue and writes what was said, as whole sentences with the
    film's pauses kept.

    The dialogue alone is transcribed (not the original mix) because music under speech
    smears the word timings, and a dub is placed by those timings. What the service heard is
    saved as it came, so a change to the sentence rules is redone without transcribing again."""

    name = "dub_transcribe"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.dub_dialogue] if ctx.options.dub_languages else []

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.dub_transcript] if ctx.options.dub_languages else []

    def config_key(self, ctx: PipelineContext) -> str:
        if not ctx.options.dub_languages:
            return "no-dub"
        return f"{self._heard_key(ctx)}|{RULES_VERSION}"

    @staticmethod
    def _heard_key(ctx: PipelineContext) -> str:
        return f"{ctx.providers.transcriber.identity}|{ctx.options.source_language}"

    def run(self, ctx: PipelineContext) -> None:
        if not ctx.options.dub_languages:
            return
        heard = self._heard(ctx)
        write_model(ctx.paths.dub_transcript, merge_sentences(heard.transcript))

    def _heard(self, ctx: PipelineContext) -> HeardTranscript:
        key = self._heard_key(ctx)
        saved = ctx.paths.dub_heard
        # Saved only counts if it was made by the same service for this very dialogue.
        if saved.exists() and saved.stat().st_mtime_ns >= ctx.paths.dub_dialogue.stat().st_mtime_ns:
            heard = read_model(saved, HeardTranscript)
            if heard.key == key:
                return heard
        ctx.media.extract_audio(ctx.paths.dub_dialogue, ctx.paths.dub_speech)
        transcript = ctx.providers.transcriber.transcribe(
            ctx.paths.dub_speech, ctx.options.source_language
        )
        heard = HeardTranscript(key=key, transcript=transcript)
        write_model(saved, heard)
        return heard
