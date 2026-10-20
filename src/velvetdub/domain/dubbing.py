"""Dubbing value types and the files a dub is built from. Pure data: no I/O, no vendor names."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from velvetdub.domain.transcript import Transcript

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


class HeardTranscript(BaseModel):
    """What the transcription service heard in the dialogue, as it said it. Kept so that changing
    how lines are shaped into sentences never means transcribing (and paying) again. `key` names
    the service and language it was made with."""

    key: str
    transcript: Transcript


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
    # How many times the voice service was asked for this line (0 for a line recorded before this
    # was counted). A line that does not fit is asked for again, a few times at most.
    takes: int = 0

    @property
    def over_slot(self) -> bool:
        return self.duration > self.slot + 0.05


class DubLines(BaseModel):
    language: str
    lines: list[DubLine]
    # Lines left as the film has them, not dubbed: crowd chants, or a line the voice could not
    # say. They cost nothing and the original sound plays there.
    kept_original: list[str] = Field(default_factory=list)


class AmbienceWindow(BaseModel):
    """A stretch of the film where an actor speaks, and how much of the original sound stays."""

    model_config = ConfigDict(frozen=True)

    start: float
    end: float
    gain: float  # 0 = silent (the dub speaks alone), 1 = the original sound untouched


class Ambience(BaseModel):
    """What to keep of the original dialogue stem under a dub.

    The stem holds every human sound the separator found: the actors, but also crowds, chanting
    and singing, which it cannot tell apart. Outside the `windows` (where an actor speaks and the
    dub takes over) it plays as it is; inside each window it plays at that window's gain."""

    model_config = ConfigDict(frozen=True)

    stem: Path
    windows: tuple[AmbienceWindow, ...]
