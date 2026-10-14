"""Filtering model.

Detection and decision are separate on purpose:

* A FilterEvent is a *detection*: what was found and where. It does not depend on who is watching.
* A FilterProfile holds one viewer's standards.
* FilterPolicy combines them into an action at playback time.

So changing what is acted on never requires reprocessing a film, and each household member
can make their own "Keep it in" choices over the same detections.
"""

from collections.abc import Iterable
from enum import IntEnum, StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FilterCategory(StrEnum):
    SWEARING = "swearing"
    BLASPHEMY = "blasphemy"
    NUDITY = "nudity"
    SEXUAL_CONTENT = "sexual_content"
    VIOLENCE = "violence"
    DRUGS_AND_DRINKING = "drugs_and_drinking"
    SCARY_SCENES = "scary_scenes"


class Severity(IntEnum):
    """On/off categories (such as blasphemy) are always detected as MILD."""

    MILD = 1
    MODERATE = 2
    STRONG = 3


class FilterAction(StrEnum):
    MUTE = "mute"
    REPLACE = "replace"
    BLUR = "blur"
    SKIP = "skip"
    SUMMARIZE = "summarize"


class Region(BaseModel):
    """A rectangle in the frame, as fractions (0-1) of its width and height."""

    model_config = ConfigDict(frozen=True)

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class FilterEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    category: FilterCategory
    severity: Severity
    start: float
    end: float
    confidence: float = Field(default=1.0, ge=0, le=1)
    source: str  # which detector found it, e.g. "wordlist" or "gemini:gemini-3.8-flash"
    note: str | None = None
    text: str | None = None  # the offending word, for mute/replace
    replacement: str | None = None  # clean substitute, if known
    region: Region | None = None  # for blur

    @model_validator(mode="after")
    def _ordered(self) -> "FilterEvent":
        if self.end < self.start:
            raise ValueError("event end must not be before start")
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start


class FilterTimeline(BaseModel):
    events: list[FilterEvent] = Field(default_factory=list)

    def sorted_events(self) -> list[FilterEvent]:
        return sorted(self.events, key=lambda e: (e.start, e.end))


class CategoryRule(BaseModel):
    """Apply `action` to events of this category at or above `min_severity`."""

    model_config = ConfigDict(frozen=True)

    action: FilterAction
    min_severity: Severity = Severity.MILD


class FilterProfile(BaseModel):
    """One viewer's standards. `owner_id` ties it to a user (a fixed local user for now)."""

    id: str
    owner_id: str
    name: str
    rules: dict[FilterCategory, CategoryRule] = Field(default_factory=dict)
    min_confidence: float = Field(default=0.0, ge=0, le=1)


class ResolvedFilter(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: FilterEvent
    action: FilterAction


# Spoken-word categories are timed to the word and padded by the player; every other category
# comes from the picture scan.
WORD_CATEGORIES = frozenset({FilterCategory.SWEARING, FilterCategory.BLASPHEMY})
# The picture scan reports whole seconds from 1 frame per second, so a scene can really begin up
# to a second before the time it gives. Cutting a little early beats cutting late, so picture
# moments are widened by this much on each side at playback (stored detections stay as found).
PICTURE_LEAD_SECONDS = 1.0
PICTURE_TAIL_SECONDS = 1.0


class FilterPolicy:
    """Decides what happens to each detection under a set of rules."""

    def action_for(self, event: FilterEvent, profile: FilterProfile) -> FilterAction | None:
        rule = profile.rules.get(event.category)
        if rule is None:
            return None
        if event.confidence < profile.min_confidence:
            return None
        if event.severity < rule.min_severity:
            return None
        return rule.action

    def resolve(self, timeline: FilterTimeline, profile: FilterProfile) -> list[ResolvedFilter]:
        resolved: list[ResolvedFilter] = []
        for event in timeline.sorted_events():
            action = self.action_for(event, profile)
            if action is not None:
                resolved.append(ResolvedFilter(event=self._padded(event), action=action))
        return sorted(resolved, key=lambda r: (r.event.start, r.event.end))

    @staticmethod
    def _padded(event: FilterEvent) -> FilterEvent:
        if event.category in WORD_CATEGORIES:
            return event
        return event.model_copy(
            update={
                "start": max(0.0, event.start - PICTURE_LEAD_SECONDS),
                "end": event.end + PICTURE_TAIL_SECONDS,
            }
        )

    @staticmethod
    def runtime_removed(resolved: Iterable[ResolvedFilter]) -> float:
        """Seconds of runtime skipped, counting overlapping skips once."""
        spans = sorted(
            (r.event.start, r.event.end) for r in resolved if r.action is FilterAction.SKIP
        )
        total = 0.0
        current_end = float("-inf")
        for start, end in spans:
            start = max(start, current_end)
            if end > start:
                total += end - start
            current_end = max(current_end, end)
        return total
