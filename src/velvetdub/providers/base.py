"""Provider interfaces.

Each external capability is an abstract class. The pipeline depends only on these, never on a
vendor SDK, so changing vendor or model is a settings change plus (at most) one new subclass.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from velvetdub.domain.dubbing import SeparatedStems, SynthesisRequest, Voice
from velvetdub.domain.filtering import FilterEvent
from velvetdub.domain.transcript import Transcript
from velvetdub.domain.translation import Translation, TranslationTone


class Provider(ABC):
    """Base for all providers. `identity` feeds pipeline cache keys, so changing the model
    or vendor automatically invalidates the stages that used it."""

    name: ClassVar[str]

    def __init__(self, model: str | None = None) -> None:
        self.model = model

    @property
    def identity(self) -> str:
        return f"{self.name}:{self.model or 'default'}"


class Transcriber(Provider):
    @abstractmethod
    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        """Word-level timestamps and speaker labels. `language=None` means auto-detect."""


class Translator(Provider):
    @abstractmethod
    def translate(
        self,
        transcript: Transcript,
        target_language: str,
        tone: TranslationTone = TranslationTone.NATURAL,
    ) -> Translation:
        """Translate every segment, keeping segment ids and filling `target_duration`."""


class Moderator(Provider):
    """Visual moderation. The pipeline cuts clips; the provider scans one at a time."""

    @abstractmethod
    def scan_clip(self, clip_path: Path, *, offset: float) -> list[FilterEvent]:
        """Detections inside one clip, with times already shifted by `offset` seconds so they
        sit on the full film's timeline."""


class TextModerator(Provider):
    """Moderation of spoken words (profanity and similar)."""

    @abstractmethod
    def scan_transcript(self, transcript: Transcript) -> list[FilterEvent]: ...


class SourceSeparator(Provider):
    """Phase 2: split dialogue from music and effects."""

    @abstractmethod
    def separate(self, audio_path: Path, out_dir: Path) -> SeparatedStems: ...


class SpeechSynthesizer(Provider):
    """Phase 2: text to speech."""

    @abstractmethod
    def list_voices(self, language: str | None = None) -> list[Voice]: ...

    @abstractmethod
    def synthesize(self, request: SynthesisRequest, dest: Path) -> Path:
        """Write audio for one line to `dest` and return it."""
