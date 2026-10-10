"""Mask filtered words in subtitles so the text matches the muted audio."""

import re
from collections.abc import Iterable

from velvetdub.domain.filtering import FilterAction, FilterCategory, ResolvedFilter
from velvetdub.subtitles.webvtt import Cue

MASKED_ACTIONS = {FilterAction.MUTE, FilterAction.REPLACE}
# Detections are timed from speech, subtitle cues are timed by line; allow a little slack.
SLACK = 0.5
_LETTERS = re.compile(r"[^\w']", re.UNICODE)


def mask_cues(cues: Iterable[Cue], filters: Iterable[ResolvedFilter]) -> list[Cue]:
    """Replace each muted word with asterisks inside the cue(s) it was spoken in.

    Only works on text in the spoken language: it matches the original words. Translated
    subtitles are left as they are.
    """
    words = [
        (f.event.start, f.event.end, _LETTERS.sub("", f.event.text or ""))
        for f in filters
        if f.action in MASKED_ACTIONS
        and f.event.category in (FilterCategory.SWEARING, FilterCategory.BLASPHEMY)
        and f.event.text
    ]
    masked: list[Cue] = []
    for cue in cues:
        text = cue.text
        for start, end, word in words:
            if word and start < cue.end + SLACK and end > cue.start - SLACK:
                text = re.sub(
                    rf"(?<!\w){re.escape(word)}(?!\w)",
                    lambda m: "*" * len(m.group(0)),
                    text,
                    flags=re.IGNORECASE,
                )
        masked.append(cue.model_copy(update={"text": text}))
    return masked
