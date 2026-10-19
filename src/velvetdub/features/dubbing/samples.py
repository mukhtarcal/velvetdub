"""Which stretches of a speaker's voice to copy."""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from velvetdub.domain.export import Span
from velvetdub.domain.transcript import Transcript

MIN_LINE = 1.0  # shorter lines make poor samples
TARGET_SECONDS = 15.0  # enough for a good copy; more adds little
MAX_PIECES = 8
MIN_SPEECH = 3.0  # a speaker with less clear speech than this borrows another's voice


def speaker_key(speaker: str | None) -> str:
    """A speaker label that is safe in a file name."""
    return re.sub(r"[^A-Za-z0-9]", "", speaker or "") or "unknown"


@dataclass
class CastPlan:
    spans: dict[str, list[Span]] = field(default_factory=dict)  # speaker -> clear stretches
    borrows: dict[str, str] = field(default_factory=dict)  # speaker -> who they borrow from


def plan_cast(transcript: Transcript) -> CastPlan:
    """Pick up to ~15 s of clear speech for each speaker. A speaker with too little (a single
    "Hey") is given the voice of whoever speaks most, rather than a poor copy."""
    lines: dict[str, list[Span]] = defaultdict(list)
    for segment in transcript.segments:
        lines[speaker_key(segment.speaker)].append((segment.start, segment.end))

    plan = CastPlan()
    totals: dict[str, float] = {}
    for speaker, spans in lines.items():
        usable = sorted((s for s in spans if s[1] - s[0] >= MIN_LINE), key=_length, reverse=True)
        chosen: list[Span] = []
        total = 0.0
        for span in usable:
            if total >= TARGET_SECONDS or len(chosen) >= MAX_PIECES:
                break
            chosen.append(span)
            total += _length(span)
        plan.spans[speaker] = sorted(chosen)
        totals[speaker] = total

    if totals:
        main = max(totals, key=lambda s: totals[s])
        for speaker, total in totals.items():
            if total < MIN_SPEECH and speaker != main:
                plan.borrows[speaker] = main
    return plan


def _length(span: Span) -> float:
    return span[1] - span[0]
