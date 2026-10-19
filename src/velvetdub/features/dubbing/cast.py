"""Copies each speaker's voice, so the dub sounds like the people in the film."""

from collections.abc import Callable
from pathlib import Path

from velvetdub.domain.dubbing import DubVoices
from velvetdub.domain.transcript import Transcript
from velvetdub.errors import ProviderError
from velvetdub.features.dubbing.samples import plan_cast
from velvetdub.media.tools import MediaTool
from velvetdub.providers.base import SpeechSynthesizer


def clone_cast(
    transcript: Transcript,
    *,
    dialogue: Path,
    sample_path: Callable[[str], Path],
    name_for: Callable[[str], str],
    synthesizer: SpeechSynthesizer,
    media: MediaTool,
) -> DubVoices:
    """One copied voice per speaker, cut from the clean dialogue (no music under it)."""
    if not synthesizer.supports_cloning:
        raise ProviderError(f"{synthesizer.name} can't copy voices, which dubbing needs.")
    plan = plan_cast(transcript)
    voices: dict[str, str] = {}
    for speaker, spans in plan.spans.items():
        if speaker in plan.borrows:
            continue
        if not spans:
            raise ProviderError("There is no clear speech to copy a voice from.")
        sample = sample_path(speaker)
        media.cut_audio(dialogue, spans, sample)
        voice = synthesizer.clone_voice(sample, name_for(speaker), transcript.language)
        voices[speaker] = voice.id
    for speaker, lender in plan.borrows.items():
        voices[speaker] = voices[lender]
    return DubVoices(provider=synthesizer.identity, voices=voices)
