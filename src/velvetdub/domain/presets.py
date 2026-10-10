"""Starting-point filter presets. The values are judgment calls meant to be tuned by use."""

from collections.abc import Callable

from velvetdub.domain.filtering import (
    CategoryRule,
    FilterAction,
    FilterCategory,
    FilterProfile,
    Severity,
)

C = FilterCategory
A = FilterAction
S = Severity


def _kids() -> dict[FilterCategory, CategoryRule]:
    return {
        C.SWEARING: CategoryRule(action=A.MUTE),
        C.BLASPHEMY: CategoryRule(action=A.MUTE),
        C.NUDITY: CategoryRule(action=A.SKIP),
        C.SEXUAL_CONTENT: CategoryRule(action=A.SKIP),
        C.VIOLENCE: CategoryRule(action=A.SKIP),
        C.DRUGS_AND_DRINKING: CategoryRule(action=A.SKIP),
        C.SCARY_SCENES: CategoryRule(action=A.SKIP),
    }


def _family() -> dict[FilterCategory, CategoryRule]:
    return {
        C.SWEARING: CategoryRule(action=A.MUTE, min_severity=S.MODERATE),
        C.BLASPHEMY: CategoryRule(action=A.MUTE),
        C.NUDITY: CategoryRule(action=A.SKIP),
        C.SEXUAL_CONTENT: CategoryRule(action=A.SKIP, min_severity=S.MODERATE),
        C.VIOLENCE: CategoryRule(action=A.SKIP, min_severity=S.STRONG),
        C.SCARY_SCENES: CategoryRule(action=A.SKIP, min_severity=S.STRONG),
    }


def _teen() -> dict[FilterCategory, CategoryRule]:
    return {
        C.SWEARING: CategoryRule(action=A.MUTE, min_severity=S.STRONG),
        C.NUDITY: CategoryRule(action=A.SKIP),
        C.SEXUAL_CONTENT: CategoryRule(action=A.SKIP, min_severity=S.STRONG),
        C.VIOLENCE: CategoryRule(action=A.SKIP, min_severity=S.STRONG),
    }


def _language_only() -> dict[FilterCategory, CategoryRule]:
    return {
        C.SWEARING: CategoryRule(action=A.MUTE),
        C.BLASPHEMY: CategoryRule(action=A.MUTE),
    }


PRESETS: dict[str, Callable[[], dict[FilterCategory, CategoryRule]]] = {
    "kids": _kids,
    "family": _family,
    "teen": _teen,
    "language_only": _language_only,
}


def profile_from_preset(preset: str, *, profile_id: str, owner_id: str, name: str) -> FilterProfile:
    try:
        rules = PRESETS[preset]()
    except KeyError:
        raise ValueError(f"Unknown preset '{preset}'. Available: {', '.join(PRESETS)}") from None
    return FilterProfile(id=profile_id, owner_id=owner_id, name=name, rules=rules)
