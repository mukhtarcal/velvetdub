"""Translations reference transcript segments by id, so timing always comes from one place."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class TranslationTone(StrEnum):
    LITERAL = "literal"
    NATURAL = "natural"
    KID_FRIENDLY = "kid_friendly"


class TranslatedSegment(BaseModel):
    """`target_duration` is the original line's length in seconds.

    Subtitles ignore it. Dubbing uses it to rephrase lines that would not fit.
    """

    model_config = ConfigDict(frozen=True)

    segment_id: str
    text: str
    target_duration: float


class Translation(BaseModel):
    language: str
    tone: TranslationTone = TranslationTone.NATURAL
    segments: list[TranslatedSegment]
