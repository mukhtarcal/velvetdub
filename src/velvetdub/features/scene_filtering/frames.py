"""Turns per-second answers about frames into filter events on the film's timeline."""

from collections.abc import Mapping, Sequence

from velvetdub.domain.filtering import FilterCategory, FilterEvent, Severity
from velvetdub.features.scene_filtering.frame_prompt import NUDITY, SEXUAL

CATEGORY_FOR_QUESTION = {
    NUDITY: (FilterCategory.NUDITY, "Exposed nudity"),
    SEXUAL: (FilterCategory.SEXUAL_CONTENT, "Sexual content"),
}
# Flagged seconds this close together are one scene (a scene is rarely flagged on every second).
MERGE_GAP_SECONDS = 4
STRONG_AT = 0.9


def _severity(probability: float) -> Severity:
    if probability >= STRONG_AT:
        return Severity.STRONG
    return Severity.MODERATE if probability >= 0.5 else Severity.MILD


def frame_events(
    per_second: Sequence[Mapping[str, float]], *, offset: float, source: str, threshold: float
) -> list[FilterEvent]:
    """`per_second[i]` holds the answers for the window around second `i` of the clip.
    `offset` is where the clip starts in the film."""
    events: list[FilterEvent] = []
    for question, (category, label) in CATEGORY_FOR_QUESTION.items():
        scenes: list[list[int]] = []
        for second, answers in enumerate(per_second):
            if answers.get(question, 0.0) < threshold:
                continue
            if scenes and second - scenes[-1][1] <= MERGE_GAP_SECONDS:
                scenes[-1][1] = second
            else:
                scenes.append([second, second])
        for first, last in scenes:
            peak = max(per_second[s].get(question, 0.0) for s in range(first, last + 1))
            events.append(
                FilterEvent(
                    id=f"vis-{offset:.0f}-{len(events)}",
                    category=category,
                    severity=_severity(peak),
                    start=offset + first,
                    end=offset + last + 1,
                    confidence=min(max(peak, 0.0), 1.0),
                    source=source,
                    note=f"{label} (peak score {peak:.2f})",
                )
            )
    return sorted(events, key=lambda e: (e.start, e.end))
