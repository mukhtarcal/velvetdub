"""How much room each dubbed line has."""

from collections.abc import Sequence

from velvetdub.domain.transcript import Segment

MIN_SLOT = 0.3  # seconds: even a one-word line gets this
BREATH = 0.1  # seconds kept clear before the next line starts
SPILL = 1.0  # a line may run this long past the original, if the gap after it allows


def slots(segments: Sequence[Segment], film_seconds: float) -> list[float]:
    """For each line, the seconds it may take: its own length plus up to `SPILL` more, but never
    into the next line. Another language is rarely the same length, and the pause after a line is
    the natural place to absorb the difference."""
    result: list[float] = []
    for index, segment in enumerate(segments):
        following = segments[index + 1].start if index + 1 < len(segments) else film_seconds
        room = min(following - segment.start - BREATH, segment.duration + SPILL)
        result.append(max(MIN_SLOT, room))
    return result
