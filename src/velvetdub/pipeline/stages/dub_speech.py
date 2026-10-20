from functools import partial
from pathlib import Path

from velvetdub.domain.dubbing import DubLines, DubVoices
from velvetdub.domain.transcript import Transcript
from velvetdub.domain.translation import Translation
from velvetdub.features.dubbing.crowd import STEP, crowd_lines
from velvetdub.features.dubbing.lines import record_lines
from velvetdub.features.dubbing.speech import LineRecorder
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.pipeline.stages.dubbing import dub_targets
from velvetdub.storage.artifacts import read_model, write_model

# Bump this when how lines are recorded changes, so existing dubs are looked at again. That costs
# credits only for lines that need recording again (see `record_lines`).
SPEECH_VERSION = "speech-2"


class DubSpeechStage(Stage):
    """Speaks every line of each dub in the copied voices, fitted to the time it has.

    This is the stage that costs voice-service credits. Each line is saved as it is recorded and
    reused on the next run, so a failure part way never means paying for the film twice. Crowd
    chants are not dubbed: the film's own sound is kept for them."""

    name = "dub_speech"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        targets = dub_targets(ctx)
        if not targets:
            return []
        translations = [ctx.paths.dub_translation(lang) for lang in targets]
        return [
            ctx.paths.dub_transcript,
            ctx.paths.dub_voices,
            ctx.paths.dub_dialogue,
            *translations,
        ]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.dub_lines(lang) for lang in dub_targets(ctx)]

    def config_key(self, ctx: PipelineContext) -> str:
        if not dub_targets(ctx):
            return "no-dub"
        languages = ",".join(dub_targets(ctx))
        return f"{ctx.providers.synthesizer.identity}|{languages}|{SPEECH_VERSION}"

    def run(self, ctx: PipelineContext) -> None:
        targets = dub_targets(ctx)
        if not targets:
            return
        transcript = read_model(ctx.paths.dub_transcript, Transcript)
        voices = read_model(ctx.paths.dub_voices, DubVoices)
        synthesizer = ctx.providers.synthesizer
        recorder = LineRecorder(synthesizer, ctx.media)
        film_seconds = ctx.manifest.duration or max((s.end for s in transcript.segments), default=0)
        # Chants are found from the sound itself: the words alone cannot tell a crowd from a person.
        levels = ctx.media.level_profile(ctx.paths.dub_dialogue, STEP)
        chants = crowd_lines(transcript.segments, levels, STEP)
        for language in targets:
            translation = read_model(ctx.paths.dub_translation(language), Translation)
            earlier = ctx.paths.dub_lines(language)
            lines = record_lines(
                transcript=transcript,
                translation=translation,
                voices=voices,
                film_seconds=film_seconds,
                recorder=recorder,
                identity=synthesizer.identity,
                line_path=partial(ctx.paths.dub_line, language),
                relative=ctx.paths.relative,
                concurrency=ctx.settings.tts_concurrency,
                skip=chants,
                previous=read_model(earlier, DubLines) if earlier.exists() else None,
            )
            write_model(earlier, lines)
