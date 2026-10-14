"""The shape the video model answers in, and how its answer becomes filter events."""

from collections.abc import Collection
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel

from velvetdub.domain.filtering import FilterCategory, FilterEvent, Severity
from velvetdub.errors import ProviderError


class VisualCategory(StrEnum):
    NUDITY = "nudity"
    SEXUAL_CONTENT = "sexual_content"
    VIOLENCE = "violence"
    DRUGS_AND_DRINKING = "drugs_and_drinking"
    SCARY_SCENES = "scary_scenes"


class Detection(BaseModel):
    start: str
    end: str
    category: VisualCategory
    severity: Literal["mild", "moderate", "strong"]
    confidence: float
    description: str


class ClipResult(BaseModel):
    detections: list[Detection]


SEVERITY = {"mild": Severity.MILD, "moderate": Severity.MODERATE, "strong": Severity.STRONG}


def parse_clock(value: str) -> float:
    """'MM:SS', 'H:MM:SS' or plain seconds -> seconds."""
    try:
        seconds = 0.0
        for part in value.strip().split(":"):
            seconds = seconds * 60 + float(part)
        return seconds
    except ValueError:
        raise ProviderError(f"Could not read timestamp '{value}' from the moderator.") from None


def to_events(
    result: ClipResult,
    *,
    offset: float,
    source: str,
    allowed: Collection[FilterCategory] | None = None,
) -> list[FilterEvent]:
    """Place a clip's detections on the full film's timeline (`offset` is the clip's start).
    Detections outside `allowed` are dropped: the model was only asked about those categories, so
    anything else is a stray answer."""
    events: list[FilterEvent] = []
    for index, found in enumerate(result.detections):
        if allowed is not None and FilterCategory(found.category.value) not in allowed:
            continue
        start = offset + parse_clock(found.start)
        end = offset + parse_clock(found.end)
        events.append(
            FilterEvent(
                id=f"vis-{offset:.0f}-{index}",
                category=FilterCategory(found.category.value),
                severity=SEVERITY[found.severity],
                start=start,
                end=max(start, end),
                confidence=min(max(found.confidence, 0.0), 1.0),
                source=source,
                note=found.description,
            )
        )
    return events
