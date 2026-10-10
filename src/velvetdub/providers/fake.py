"""Deterministic offline providers for tests and trying the pipeline without API keys.

Select with e.g. TRANSCRIPTION_PROVIDER=fake.
"""

from pathlib import Path

from velvetdub.config.settings import Settings
from velvetdub.domain.filtering import FilterCategory, FilterEvent, Severity
from velvetdub.domain.transcript import Segment, Transcript, Word
from velvetdub.domain.translation import TranslatedSegment, Translation, TranslationTone
from velvetdub.providers.base import Moderator, Transcriber, Translator
from velvetdub.providers.registry import moderators, transcribers, translators


class FakeTranscriber(Transcriber):
    name = "fake"

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        lines = [
            ("Hello there, friend.", 1.0, 3.0),
            ("What the hell is that?", 4.0, 6.0),
        ]
        segments = []
        for i, (text, start, end) in enumerate(lines):
            tokens = text.split()
            step = (end - start) / len(tokens)
            words = tuple(
                Word(text=t, start=start + n * step, end=start + (n + 1) * step)
                for n, t in enumerate(tokens)
            )
            segments.append(
                Segment(id=f"s{i}", start=start, end=end, text=text, speaker="A", words=words)
            )
        return Transcript(language=language or "en", segments=segments)


class FakeTranslator(Translator):
    name = "fake"

    def translate(
        self,
        transcript: Transcript,
        target_language: str,
        tone: TranslationTone = TranslationTone.NATURAL,
    ) -> Translation:
        return Translation(
            language=target_language,
            tone=tone,
            segments=[
                TranslatedSegment(
                    segment_id=s.id,
                    text=f"[{target_language}] {s.text}",
                    target_duration=s.duration,
                )
                for s in transcript.segments
            ],
        )


class FakeModerator(Moderator):
    name = "fake"

    def scan_clip(self, clip_path: Path, *, offset: float) -> list[FilterEvent]:
        return [
            FilterEvent(
                id=f"vis-{offset:.0f}",
                category=FilterCategory.VIOLENCE,
                severity=Severity.STRONG,
                start=offset + 10.0,
                end=offset + 20.0,
                confidence=0.9,
                source=self.identity,
                note="fake detection",
            )
        ]


@transcribers.register("fake")
def _transcriber(settings: Settings) -> Transcriber:
    return FakeTranscriber()


@translators.register("fake")
def _translator(settings: Settings) -> Translator:
    return FakeTranslator()


@moderators.register("fake")
def _moderator(settings: Settings) -> Moderator:
    return FakeModerator(settings.moderation_model)
