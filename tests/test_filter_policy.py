import pytest

from velvetdub.domain.filtering import (
    CategoryRule,
    FilterAction,
    FilterCategory,
    FilterEvent,
    FilterPolicy,
    FilterProfile,
    FilterTimeline,
    Severity,
)
from velvetdub.domain.presets import PRESETS, profile_from_preset


def event(
    category: FilterCategory = FilterCategory.VIOLENCE,
    severity: Severity = Severity.STRONG,
    start: float = 0,
    end: float = 10,
    confidence: float = 1.0,
) -> FilterEvent:
    return FilterEvent(
        id=f"{category}-{start}",
        category=category,
        severity=severity,
        start=start,
        end=end,
        confidence=confidence,
        source="test",
    )


def profile(**rules: CategoryRule) -> FilterProfile:
    return FilterProfile(
        id="p", owner_id="u", name="Test", rules={FilterCategory(k): v for k, v in rules.items()}
    )


policy = FilterPolicy()


def test_no_rule_means_no_action() -> None:
    assert policy.action_for(event(), profile()) is None


def test_action_applies_at_or_above_min_severity() -> None:
    p = profile(violence=CategoryRule(action=FilterAction.SKIP, min_severity=Severity.MODERATE))
    assert policy.action_for(event(severity=Severity.MILD), p) is None
    assert policy.action_for(event(severity=Severity.MODERATE), p) is FilterAction.SKIP
    assert policy.action_for(event(severity=Severity.STRONG), p) is FilterAction.SKIP


def test_low_confidence_detections_are_ignored_when_profile_requires_more() -> None:
    p = profile(violence=CategoryRule(action=FilterAction.SKIP)).model_copy(
        update={"min_confidence": 0.8}
    )
    assert policy.action_for(event(confidence=0.5), p) is None


def test_same_detections_give_different_results_per_profile() -> None:
    timeline = FilterTimeline(events=[event(FilterCategory.SWEARING, Severity.MILD)])
    strict = profile(swearing=CategoryRule(action=FilterAction.MUTE))
    relaxed = profile(swearing=CategoryRule(action=FilterAction.MUTE, min_severity=Severity.STRONG))
    assert len(policy.resolve(timeline, strict)) == 1
    assert policy.resolve(timeline, relaxed) == []


def test_runtime_removed_counts_overlaps_once() -> None:
    p = profile(violence=CategoryRule(action=FilterAction.SKIP))
    timeline = FilterTimeline(
        events=[event(start=0, end=10), event(start=5, end=15), event(start=20, end=25)]
    )
    assert policy.runtime_removed(policy.resolve(timeline, p)) == 20.0


def test_muted_words_do_not_count_as_removed_runtime() -> None:
    p = profile(swearing=CategoryRule(action=FilterAction.MUTE))
    timeline = FilterTimeline(events=[event(FilterCategory.SWEARING, Severity.STRONG, 0, 1)])
    assert policy.runtime_removed(policy.resolve(timeline, p)) == 0.0


def test_event_end_before_start_is_rejected() -> None:
    with pytest.raises(ValueError):
        event(start=5, end=1)


@pytest.mark.parametrize("preset", list(PRESETS))
def test_every_preset_builds_a_profile(preset: str) -> None:
    built = profile_from_preset(preset, profile_id="x", owner_id="u", name=preset)
    assert built.rules


def test_unknown_preset_lists_the_options() -> None:
    with pytest.raises(ValueError, match="kids"):
        profile_from_preset("nope", profile_id="x", owner_id="u", name="n")
