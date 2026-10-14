from pathlib import Path

from velvetdub.domain.manifest import SubtitleTrack
from velvetdub.domain.transcript import Transcript
from velvetdub.domain.translation import Translation
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.storage.artifacts import read_model
from velvetdub.subtitles.webvtt import Cue, format_webvtt


class SubtitlesStage(Stage):
    """Writes complete, unfiltered subtitles.

    Masking filtered words (`*****`) depends on what the viewer keeps in, so it happens at playback
    and export time, not here.
    """

    name = "subtitles"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.transcript, *self._translations(ctx)]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.subtitles(lang) for lang in ctx.options.subtitle_languages]

    def config_key(self, ctx: PipelineContext) -> str:
        return ",".join(ctx.options.subtitle_languages)

    @staticmethod
    def _translations(ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.translation(lang) for lang in ctx.options.subtitle_languages]

    def run(self, ctx: PipelineContext) -> None:
        transcript = read_model(ctx.paths.transcript, Transcript)
        timing = {s.id: s for s in transcript.segments}
        for language in ctx.options.subtitle_languages:
            translation = read_model(ctx.paths.translation(language), Translation)
            cues = [
                Cue(start=timing[t.segment_id].start, end=timing[t.segment_id].end, text=t.text)
                for t in translation.segments
            ]
            out = ctx.paths.subtitles(language)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(format_webvtt(cues), encoding="utf-8")
            ctx.manifest.upsert_subtitle_track(
                SubtitleTrack(language=language, path=ctx.paths.relative(out))
            )
