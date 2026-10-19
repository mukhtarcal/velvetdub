"""Translates a transcript in batches, checks every line came back, and retries skipped ones."""

from collections.abc import Iterator, Sequence

from pydantic import BaseModel

from velvetdub.domain.languages import language_for_model
from velvetdub.domain.transcript import Segment, Transcript
from velvetdub.domain.translation import TranslatedSegment, Translation, TranslationTone
from velvetdub.errors import ProviderError
from velvetdub.features.translation.prompt import DUBBING_RULES, SYSTEM_PROMPT, TONE_INSTRUCTIONS
from velvetdub.providers.base import TextGenerator

BATCH_SIZE = 40
CONTEXT_LINES = 4


class TranslatedLine(BaseModel):
    id: str
    text: str


class TranslatedBatch(BaseModel):
    lines: list[TranslatedLine]


def batches(
    segments: Sequence[Segment], size: int
) -> Iterator[tuple[list[Segment], list[Segment]]]:
    """Yield (batch, context) pairs. Context is the few lines just before the batch."""
    for start in range(0, len(segments), size):
        yield (
            list(segments[start : start + size]),
            list(segments[max(0, start - CONTEXT_LINES) : start]),
        )


class Translator:
    def __init__(self, generator: TextGenerator) -> None:
        self._generator = generator

    @property
    def identity(self) -> str:
        return self._generator.identity

    def translate(
        self,
        transcript: Transcript,
        target_language: str,
        tone: TranslationTone = TranslationTone.NATURAL,
        *,
        for_dubbing: bool = False,
    ) -> Translation:
        """`for_dubbing` writes lines to be spoken in the time each original line took, instead
        of lines to be read as subtitles."""
        translated: dict[str, str] = {}
        for batch, context in batches(transcript.segments, BATCH_SIZE):
            texts = self._translate_batch(
                batch, context, transcript.language, target_language, tone, for_dubbing
            )
            missing = [s for s in batch if s.id not in texts]
            if missing:  # one retry for lines the model skipped
                texts.update(
                    self._translate_batch(
                        missing, context, transcript.language, target_language, tone, for_dubbing
                    )
                )
            still_missing = [s.id for s in batch if s.id not in texts]
            if still_missing:
                raise ProviderError(f"Translation skipped lines: {', '.join(still_missing)}")
            translated.update(texts)

        return Translation(
            language=target_language,
            tone=tone,
            segments=[
                TranslatedSegment(
                    segment_id=s.id, text=translated[s.id], target_duration=s.duration
                )
                for s in transcript.segments
            ],
        )

    def _translate_batch(
        self,
        batch: Sequence[Segment],
        context: Sequence[Segment],
        source_language: str,
        target_language: str,
        tone: TranslationTone,
        for_dubbing: bool,
    ) -> dict[str, str]:
        lines = [f"[context] {s.text}" for s in context]
        if for_dubbing:
            lines += [f"[{s.id}] ({s.duration:.1f}s) {s.text}" for s in batch]
        else:
            lines += [f"[{s.id}] {s.text}" for s in batch]
        prompt = (
            f"Source language: {source_language}\n"
            f"Target language: {language_for_model(target_language)}\n"
            f"{TONE_INSTRUCTIONS[tone]}\n\n" + "\n".join(lines)
        )
        system = SYSTEM_PROMPT + (DUBBING_RULES if for_dubbing else "")
        result = self._generator.generate(system, prompt, TranslatedBatch)
        return {line.id: line.text for line in result.lines}
