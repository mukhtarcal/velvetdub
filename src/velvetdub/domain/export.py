"""Turns the cuts a viewer settled on into an edit: which parts of the film to keep, and which
stretches of sound to silence. Pure arithmetic, so it can be tested without any video."""

import hashlib
import json
from collections.abc import Iterable, Sequence

from pydantic import BaseModel, ConfigDict

from velvetdub.domain.filtering import FilterAction, ResolvedFilter

Span = tuple[float, float]

# Spoken words are muted a little early and a little late, as the player does: transcript word
# starts run late, so a mute that begins exactly on the stored time lets the start of the word out.
MUTE_LEAD_SECONDS = 0.25
MUTE_TAIL_SECONDS = 0.12
# Skips closer together than this are one cut, so a blink of picture is not left between them.
MERGE_GAP_SECONDS = 0.25
# A leftover piece shorter than this is dropped rather than flashing past.
MIN_KEEP_SECONDS = 0.1
# Bump this when the way a copy is made changes in a way you can see or hear, so copies made the
# old way count as out of date and are made again.
#   2: sound cut to the sample (it was cut in 23 ms steps, which added up over many cuts), and
#      the picture's start offset kept (it had been moved 2 frames against the sound).
RENDER_VERSION = 2


class EditPlan(BaseModel):
    """`keep` and `mute` are in the original film's time, in order, without overlaps."""

    model_config = ConfigDict(frozen=True)

    keep: list[Span]
    mute: list[Span]
    source_duration: float

    @property
    def output_duration(self) -> float:
        return sum(end - start for start, end in self.keep)

    @property
    def removed(self) -> float:
        return self.source_duration - self.output_duration

    @property
    def cuts(self) -> int:
        """How many separate pieces were taken out."""
        return len(self._removed_spans())

    def _removed_spans(self) -> list[Span]:
        spans: list[Span] = []
        cursor = 0.0
        for start, end in self.keep:
            if start > cursor:
                spans.append((cursor, start))
            cursor = end
        if cursor < self.source_duration:
            spans.append((cursor, self.source_duration))
        return spans

    def fingerprint(self) -> str:
        """Same cuts, same way of making the copy, same fingerprint: an unchanged export is never
        made twice."""
        text = json.dumps([RENDER_VERSION, self.keep, self.mute, round(self.source_duration, 3)])
        return hashlib.sha256(text.encode()).hexdigest()[:32]


def _merge(spans: Iterable[Span], gap: float) -> list[Span]:
    merged: list[Span] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1] + gap:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _clamp(span: Span, duration: float) -> Span | None:
    start, end = max(0.0, span[0]), min(duration, span[1])
    return (start, end) if end > start else None


def _inside(span: Span, covers: Sequence[Span]) -> bool:
    return any(c_start <= span[0] and span[1] <= c_end for c_start, c_end in covers)


def plan_edit(filters: Iterable[ResolvedFilter], duration: float) -> EditPlan:
    """`filters` are the cuts still in force: what the viewer left in has already been removed."""
    skips: list[Span] = []
    mutes: list[Span] = []
    for resolved in filters:
        event = resolved.event
        if resolved.action is FilterAction.SKIP:
            skips.append((event.start, event.end))
        elif resolved.action in (FilterAction.MUTE, FilterAction.REPLACE):
            mutes.append((event.start - MUTE_LEAD_SECONDS, event.end + MUTE_TAIL_SECONDS))

    cut = _merge((s for s in (_clamp(s, duration) for s in skips) if s), MERGE_GAP_SECONDS)

    keep: list[Span] = []
    cursor = 0.0
    for start, end in [*cut, (duration, duration)]:
        if start - cursor >= MIN_KEEP_SECONDS:
            keep.append((cursor, start))
        cursor = max(cursor, end)

    silenced = _merge((m for m in (_clamp(m, duration) for m in mutes) if m), 0.0)
    return EditPlan(
        keep=keep,
        mute=[m for m in silenced if not _inside(m, cut)],
        source_duration=duration,
    )
