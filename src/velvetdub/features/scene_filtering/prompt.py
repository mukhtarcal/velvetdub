"""What the video-model scan looks for, built from the categories you chose. This is a product
decision, not a vendor detail: any video model is given these same instructions."""

from collections.abc import Iterable

from velvetdub.domain.filtering import FilterCategory
from velvetdub.features.scene_filtering.categories import SCENE_DESCRIPTIONS, in_scan_order

_INTRO = """You are reviewing a clip from a film or TV episode so that families can skip parts
they would rather not watch. List every moment that contains any of these:
"""

_OUTPUT = """
For each moment give its start and end as MM:SS from the START OF THIS CLIP (not the film), the
category it belongs to, a severity (mild, moderate or strong), a confidence from 0 to 1, and a
short neutral description. Cover the whole moment, from when it begins to when it clearly ends.

Be conservative: a missed moment is worse than an extra one, so include anything doubtful with a
lower confidence. Judge only what you can see. Report only the kinds listed above, and do not
report swearing; spoken words are handled elsewhere. If the clip has none of these, return an
empty list."""


def build_prompt(categories: Iterable[FilterCategory]) -> str:
    """The scan instructions for exactly these categories (no others are mentioned)."""
    lines = [f"- {c.value}: {SCENE_DESCRIPTIONS[c]}" for c in in_scan_order(categories)]
    return _INTRO + "\n".join(lines) + "\n" + _OUTPUT
