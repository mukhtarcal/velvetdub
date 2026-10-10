"""Transcript: the single source of truth that subtitles, filters and dubbing all read."""

from pydantic import BaseModel, ConfigDict, model_validator


class Word(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    start: float
    end: float
    confidence: float | None = None


class Segment(BaseModel):
    """One spoken line. `speaker` is a diarization label such as "A", or None if unknown."""

    model_config = ConfigDict(frozen=True)

    id: str
    start: float
    end: float
    text: str
    speaker: str | None = None
    words: tuple[Word, ...] = ()

    @model_validator(mode="after")
    def _ordered(self) -> "Segment":
        if self.end < self.start:
            raise ValueError("segment end must not be before start")
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start


class Transcript(BaseModel):
    language: str
    segments: list[Segment]
