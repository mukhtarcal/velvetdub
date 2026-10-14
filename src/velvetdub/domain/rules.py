"""What happens to a detection by default: everything found is acted on, spoken words are muted
and every kind of scene is skipped. Viewers do not pick a standard; they leave in what they are
happy to watch ("Keep it in"), which is stored per title (see `services/overrides.py`)."""

from velvetdub.domain.filtering import CategoryRule, FilterAction, FilterCategory, FilterProfile

DEFAULT_RULES: dict[FilterCategory, CategoryRule] = {
    category: CategoryRule(
        action=FilterAction.MUTE
        if category in (FilterCategory.SWEARING, FilterCategory.BLASPHEMY)
        else FilterAction.SKIP
    )
    for category in FilterCategory
}


def default_profile(owner_id: str) -> FilterProfile:
    return FilterProfile(id="default", owner_id=owner_id, name="Default", rules=dict(DEFAULT_RULES))
