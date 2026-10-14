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
from velvetdub.domain.rules import DEFAULT_RULES, default_profile


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
    # Padded by a second each side: 0-11 and 4-16 merge (clamped at 0), plus 19-26
    assert policy.runtime_removed(policy.resolve(timeline, p)) == 23.0


def test_muted_words_do_not_count_as_removed_runtime() -> None:
    p = profile(swearing=CategoryRule(action=FilterAction.MUTE))
    timeline = FilterTimeline(events=[event(FilterCategory.SWEARING, Severity.STRONG, 0, 1)])
    assert policy.runtime_removed(policy.resolve(timeline, p)) == 0.0


def test_event_end_before_start_is_rejected() -> None:
    with pytest.raises(ValueError):
        event(start=5, end=1)


def test_by_default_every_kind_of_moment_is_acted_on() -> None:
    assert set(DEFAULT_RULES) == set(FilterCategory)
    mine = default_profile("u")
    assert mine.owner_id == "u"
    assert DEFAULT_RULES[FilterCategory.SWEARING].action is FilterAction.MUTE
    assert DEFAULT_RULES[FilterCategory.BLASPHEMY].action is FilterAction.MUTE
    for category in FilterCategory:
        assert DEFAULT_RULES[category].min_severity is Severity.MILD  # even mild is acted on
        if category not in (FilterCategory.SWEARING, FilterCategory.BLASPHEMY):
            assert DEFAULT_RULES[category].action is FilterAction.SKIP


def test_picture_moments_are_widened_by_a_second_each_side_at_playback() -> None:
    p = profile(nudity=CategoryRule(action=FilterAction.SKIP))
    timeline = FilterTimeline(events=[event(FilterCategory.NUDITY, Severity.STRONG, 78, 102)])
    (resolved,) = policy.resolve(timeline, p)
    assert (resolved.event.start, resolved.event.end) == (77.0, 103.0)
    assert timeline.events[0].start == 78  # the stored detection is unchanged


def test_padding_never_goes_before_the_start_of_the_film() -> None:
    p = profile(violence=CategoryRule(action=FilterAction.SKIP))
    (resolved,) = policy.resolve(FilterTimeline(events=[event(start=0.4, end=5)]), p)
    assert resolved.event.start == 0.0


def test_muted_words_are_not_padded_by_the_policy() -> None:
    p = profile(swearing=CategoryRule(action=FilterAction.MUTE))
    timeline = FilterTimeline(events=[event(FilterCategory.SWEARING, Severity.STRONG, 30, 30.4)])
    (resolved,) = policy.resolve(timeline, p)
    assert (resolved.event.start, resolved.event.end) == (30.0, 30.4)
