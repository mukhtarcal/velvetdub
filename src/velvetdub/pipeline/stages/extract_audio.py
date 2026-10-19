from pathlib import Path

from velvetdub.domain.manifest import AudioTrack, TrackKind
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage


class ExtractAudioStage(Stage):
    """Always notes the film's length and registers its own sound as the "original" track (the
    player and the library need both). The audio is only extracted, for the transcription
    service, when the dialogue is going to be transcribed."""

    name = "extract_audio"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.source]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.original_audio] if ctx.options.needs_transcript else []

    def config_key(self, ctx: PipelineContext) -> str:
        return "audio" if ctx.options.needs_transcript else "length-only"

    def run(self, ctx: PipelineContext) -> None:
        if ctx.options.needs_transcript:
            ctx.media.extract_audio(ctx.paths.source, ctx.paths.original_audio)
        ctx.manifest.duration = ctx.media.probe_duration(ctx.paths.source)
        # The player plays the film's own sound straight from the video, so this track points at
        # the film itself, not at the small copy made for transcription.
        ctx.manifest.upsert_audio_track(
            AudioTrack(
                id="original",
                label="Original",
                language=None,
                kind=TrackKind.ORIGINAL,
                path=ctx.paths.relative(ctx.paths.source),
            )
        )
