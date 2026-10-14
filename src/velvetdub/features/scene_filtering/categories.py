"""The kinds of moment the picture scan can look for, in the order the UI offers them.

This is a product decision, not a vendor detail: every scanner is asked about the same kinds, and
only the ones you chose.
"""

from collections.abc import Iterable

from velvetdub.domain.filtering import FilterCategory

PICTURE_CATEGORIES: tuple[FilterCategory, ...] = (
    FilterCategory.NUDITY,
    FilterCategory.SEXUAL_CONTENT,
    FilterCategory.SCARY_SCENES,
    FilterCategory.VIOLENCE,
)

# One line per category, appended to the video-model prompt when that category is chosen.
SCENE_DESCRIPTIONS: dict[FilterCategory, str] = {
    FilterCategory.NUDITY: "partial or full nudity",
    FilterCategory.SEXUAL_CONTENT: (
        "kissing that turns sexual, sex scenes, strong sexual innuendo shown on screen"
    ),
    FilterCategory.SCARY_SCENES: "jump scares, frightening or disturbing imagery",
    FilterCategory.VIOLENCE: "fights, weapons used on people, blood, injury, gore",
}


def in_scan_order(categories: Iterable[FilterCategory]) -> list[FilterCategory]:
    """Only the picture categories, without duplicates, in a fixed order. A fixed order keeps the
    prompt and the scan key the same however the choices were ticked."""
    chosen = set(categories)
    return [c for c in PICTURE_CATEGORIES if c in chosen]
