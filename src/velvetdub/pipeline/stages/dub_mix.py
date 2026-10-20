from pathlib import Path

from velvetdub.domain.dubbing import Ambience, DubLines, Placement
from velvetdub.domain.languages import language_name
from velvetdub.domain.manifest import AudioTrack, TrackKind
from velvetdub.domain.transcript import Transcript
from velvetdub.features.dubbing.ambience import plan_ambience, speech_windows
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.pipeline.stages.dubbing import dub_targets
from velvetdub.storage.artifacts import read_model

# Bump this when how the dub is mixed changes, so existing dubs are mixed again (it costs no
# credits: every line is already recorded).
MIX_VERSION = "mix-2"


def dub_track_id(language: str) -> str:
    return f"dub-{language}"


class DubMixStage(Stage):
    """Lays the spoken lines over the film's music and effects and saves each dub as an audio
    track the player can switch to.

    Two things keep it faithful to the film. The original sound is kept wherever no actor is
    speaking, so crowds, chanting and singing (which the separator files under "dialogue") are
    not lost. And the dub is made as loud as the film, so switching tracks does not change the
    volume."""

    name = "dub_mix"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        targets = dub_targets(ctx)
        if not targets:
            return []
        lines = (ctx.paths.dub_lines(lang) for lang in targets)
        return [
            ctx.paths.dub_background,
            ctx.paths.dub_dialogue,
            ctx.paths.dub_transcript,
            ctx.paths.source,
            *lines,
        ]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.audio_track(dub_track_id(lang)) for lang in dub_targets(ctx)]

    def config_key(self, ctx: PipelineContext) -> str:
        languages = ",".join(dub_targets(ctx))
        if not languages:
            return "no-dub"
        settings = ctx.settings
        crowd = f"crowd:{settings.dub_crowd_bed}" if settings.dub_keep_crowd else "no-crowd"
        return f"{languages}|{crowd}|{MIX_VERSION}"

    def run(self, ctx: PipelineContext) -> None:
        targets = dub_targets(ctx)
        if not targets:
            return
        transcript = read_model(ctx.paths.dub_transcript, Transcript)
        keep_crowd = ctx.settings.dub_keep_crowd
        levels = ctx.media.level_profile(ctx.paths.dub_dialogue) if keep_crowd else []
        film_loudness = ctx.media.measure_loudness(ctx.paths.source)
        for language in targets:
            lines = read_model(ctx.paths.dub_lines(language), DubLines)
            spoken = {line.segment_id for line in lines.lines}
            ambience = None
            if keep_crowd:
                windows = speech_windows(s for s in transcript.segments if s.id in spoken)
                planned = plan_ambience(windows, levels, ctx.settings.dub_crowd_bed)
                ambience = Ambience(stem=ctx.paths.dub_dialogue, windows=planned)
            placements = [
                Placement(path=ctx.paths.root / line.path, start=line.start) for line in lines.lines
            ]
            dest = ctx.paths.audio_track(dub_track_id(language))
            ctx.media.mix_dub(
                placements,
                ctx.paths.dub_background,
                dest,
                ambience=ambience,
                loudness=film_loudness,
            )
            ctx.manifest.upsert_audio_track(
                AudioTrack(
                    id=dub_track_id(language),
                    label=f"{language_name(language)} dub",
                    language=language,
                    kind=TrackKind.DUB,
                    path=ctx.paths.relative(dest),
                )
            )
