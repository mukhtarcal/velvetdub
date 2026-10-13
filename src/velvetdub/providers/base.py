"""Provider interfaces.

Each external capability is an abstract class. The pipeline depends only on these, never on a
vendor SDK, so changing vendor or model is a settings change plus (at most) one new subclass.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from velvetdub.domain.dubbing import SeparatedStems, SynthesisRequest, Voice
from velvetdub.domain.filtering import FilterEvent
from velvetdub.domain.frames import FrameJudgement, FrameQuestion
from velvetdub.domain.transcript import Transcript
from velvetdub.domain.usage import TokenUsage


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


class TextGenerator(Provider):
    """A language model that answers a text prompt in a fixed structure. What to ask, and what
    to do with the answer, belongs to the feature using it (see `velvetdub.features`)."""

    @abstractmethod
    def generate[T: BaseModel](self, system: str, prompt: str, schema: type[T]) -> T:
        """Answer `prompt` under the `system` instructions, as an instance of `schema`."""


class VideoAnalyzer(Provider):
    """A model that watches a short video clip and answers in a fixed structure."""

    last_usage = TokenUsage()  # tokens the latest analysis used, when the service reports them

    @abstractmethod
    def analyze_clip[T: BaseModel](self, clip_path: Path, instructions: str, schema: type[T]) -> T:
        """Watch the clip, follow `instructions`, and answer as an instance of `schema`."""


class FrameJudge(Provider):
    """A model that looks at a few frames and says how likely each yes/no condition is."""

    @abstractmethod
    def judge(
        self, frames: Sequence[Path], intro: str, questions: Sequence[FrameQuestion]
    ) -> FrameJudgement:
        """Show the frames (in order) with `intro`, and answer every question with a 0-1 chance."""


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
