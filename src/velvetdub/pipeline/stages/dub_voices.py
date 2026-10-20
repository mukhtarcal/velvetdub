from pathlib import Path

from velvetdub.domain.dubbing import DubVoices
from velvetdub.domain.transcript import Transcript
from velvetdub.features.dubbing.cast import clone_cast
from velvetdub.features.dubbing.samples import speaker_key
from velvetdub.pipeline.context import PipelineContext
from velvetdub.pipeline.stage import Stage
from velvetdub.pipeline.stages.dubbing import dub_targets
from velvetdub.storage.artifacts import read_model, write_model


class DubVoicesStage(Stage):
    """Copies each speaker's voice from a few seconds of the clean dialogue."""

    name = "dub_voices"

    def inputs(self, ctx: PipelineContext) -> list[Path]:
        if not dub_targets(ctx):
            return []
        return [ctx.paths.dub_transcript, ctx.paths.dub_dialogue]

    def outputs(self, ctx: PipelineContext) -> list[Path]:
        return [ctx.paths.dub_voices] if dub_targets(ctx) else []

    def config_key(self, ctx: PipelineContext) -> str:
        return ctx.providers.synthesizer.identity if dub_targets(ctx) else "no-dub"

    def run(self, ctx: PipelineContext) -> None:
        if not dub_targets(ctx):
            return
        transcript = read_model(ctx.paths.dub_transcript, Transcript)
        synthesizer = ctx.providers.synthesizer
        # The voices belong to the people in the film, not to how their lines were cut up, so a
        # change to the script keeps them. Copying a voice again would also change every line's
        # voice and mean recording the whole dub again.
        if ctx.paths.dub_voices.exists():
            kept = read_model(ctx.paths.dub_voices, DubVoices)
            speakers = {speaker_key(s.speaker) for s in transcript.segments}
            if kept.provider == synthesizer.identity and speakers <= set(kept.voices):
                return
        title = ctx.manifest.title_id
        voices = clone_cast(
            transcript,
            dialogue=ctx.paths.dub_dialogue,
            sample_path=ctx.paths.dub_sample,
            name_for=lambda speaker: f"velvetdub-{title}-{speaker_key(speaker)}",
            synthesizer=synthesizer,
            media=ctx.media,
        )
        write_model(ctx.paths.dub_voices, voices)
