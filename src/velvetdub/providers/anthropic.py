"""Claude translation (structured output, so every line id is validated)."""

from collections.abc import Iterator, Sequence

import anthropic
from pydantic import BaseModel

from velvetdub.config.settings import Settings
from velvetdub.domain.transcript import Segment, Transcript
from velvetdub.domain.translation import TranslatedSegment, Translation, TranslationTone
from velvetdub.errors import ProviderError
from velvetdub.providers.base import Translator
from velvetdub.providers.keys import require_key
from velvetdub.providers.registry import translators

BATCH_SIZE = 40
CONTEXT_LINES = 4

SYSTEM_PROMPT = """You translate film and TV dialogue into subtitles.

Rules:
- Translate each numbered line on its own. Never merge, split, reorder or drop lines.
- Return every id exactly once, with the translated text for that line.
- Keep the speaker's meaning, register and emotional force. Keep names unchanged.
- Keep profanity at the same strength as the original; do not censor or soften it unless the
  tone below says so. A separate system handles filtering.
- Write natural, speakable text, not a word-for-word copy.
- Lines marked as context are for understanding only; do not translate or return them."""

TONE_INSTRUCTIONS: dict[TranslationTone, str] = {
    TranslationTone.LITERAL: "Stay close to the original wording.",
    TranslationTone.NATURAL: "Prefer the way people really talk in the target language.",
    TranslationTone.KID_FRIENDLY: (
        "Use gentle, child-appropriate wording. Replace swearing and crude language with mild "
        "alternatives."
    ),
}


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


class AnthropicTranslator(Translator):
    name = "anthropic"

    def __init__(self, client: anthropic.Anthropic, model: str) -> None:
        super().__init__(model)
        self._client = client

    def translate(
        self,
        transcript: Transcript,
        target_language: str,
        tone: TranslationTone = TranslationTone.NATURAL,
    ) -> Translation:
        translated: dict[str, str] = {}
        for batch, context in batches(transcript.segments, BATCH_SIZE):
            texts = self._translate_batch(
                batch, context, transcript.language, target_language, tone
            )
            missing = [s for s in batch if s.id not in texts]
            if missing:  # one retry for lines the model skipped
                texts.update(
                    self._translate_batch(
                        missing, context, transcript.language, target_language, tone
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
    ) -> dict[str, str]:
        """The only method that talks to the network (tests replace it)."""
        lines = [f"[context] {s.text}" for s in context]
        lines += [f"[{s.id}] {s.text}" for s in batch]
        prompt = (
            f"Translate from {source_language} to {target_language} (language code).\n"
            f"{TONE_INSTRUCTIONS[tone]}\n\n" + "\n".join(lines)
        )
        response = self._client.messages.parse(
            model=self.model or "",
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_format=TranslatedBatch,
        )
        if response.stop_reason == "refusal":
            raise ProviderError("Claude declined to translate this dialogue.")
        if response.parsed_output is None:
            raise ProviderError("Claude returned no usable translation.")
        return {line.id: line.text for line in response.parsed_output.lines}


@translators.register("anthropic")
def _create(settings: Settings) -> Translator:
    key = require_key(settings.anthropic_api_key, "ANTHROPIC_API_KEY")
    return AnthropicTranslator(anthropic.Anthropic(api_key=key), settings.translation_model)
