"""Dubbing value types and the files a dub is built from. Pure data: no I/O, no vendor names."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

# Every spoken line is a mono 16-bit WAV at this rate, whichever voice service made it, so the
# lines can be joined into one track without converting each one.
LINE_SAMPLE_RATE = 24000


class Voice(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    language: str | None = None


class SynthesisRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    voice_id: str
    language: str
    speed: float = 1.0  # 1.0 is the voice's natural pace; above 1.0 is faster


class SeparatedStems(BaseModel):
    model_config = ConfigDict(frozen=True)

    dialogue: Path
    background: Path


class Placement(BaseModel):
    """One spoken line (a WAV file) and where it starts in the film."""

    model_config = ConfigDict(frozen=True)

    path: Path
    start: float


class DubVoices(BaseModel):
    """Which voice speaks for each speaker in this film.

    `provider` is the identity of the service that made them: voices made by another service
    (or model) are not reused."""

    provider: str
    voices: dict[str, str] = Field(default_factory=dict)  # speaker label -> voice id


class DubLine(BaseModel):
    """One recorded line of a dub. `key` ties the audio to the text, voice and room that made it,
    so a line is only recorded again (and paid for again) when one of them changes."""

    segment_id: str
    start: float  # where the original line starts
    slot: float  # the room this line has before the next one starts
    text: str
    voice_id: str
    key: str
    duration: float
    path: str  # relative to the title folder

    @property
    def over_slot(self) -> bool:
        return self.duration > self.slot + 0.05


class DubLines(BaseModel):
    language: str
    lines: list[DubLine]
