"""Spotting crowd chants, so they are left as they are instead of being dubbed.

The transcription service writes a crowd chanting "One! Two! Three!" down as a few brief words
(and misses some), each given to a different "speaker". Dubbing those would put a different
cloned voice on every shout, at times that don't match the chant. They are not dialogue: the
film's own sound is better. What marks them: the words are brief, the sound is loud, and it is
one long burst, much longer than the words. Quiet lines in a noisy room are not chants, however
long the noise lasts, which is why loudness is part of the rule."""

from collections.abc import Iterable, Sequence

from velvetdub.domain.transcript import Segment

STEP = 0.1  # seconds per reading of the dialogue stem's loudness
BRIEF = 1.2  # seconds: a longer line is a person talking
LOUD_DB = -30.0  # a chant is a crowd's roar; a quiet burst is just the room
DROP_DB = 12.0  # the burst lasts while the sound stays within this of its peak
RATIO = 3.5  # and it must last this many times longer than the words
MIN_BURST = 1.0  # seconds, and never shorter than this


def crowd_burst(start: float, end: float, levels: Sequence[float], step: float = STEP) -> bool:
    """Whether the brief words at `start`-`end` are part of a long, loud burst of crowd noise.
    `levels` is the loudness (dB) of the dialogue stem, one reading every `step` seconds."""
    speech = end - start
    if speech > BRIEF or not levels:
        return False
    # Look a little either side of the words: the service often places a chanted word at the very
    # edge of the burst it belongs to.
    first = max(0, int((start - 0.15) / step))
    last = min(len(levels), int((end + 0.35) / step) + 1)
    if first >= last:
        return False
    peak_at = max(range(first, last), key=lambda i: levels[i])
    peak = levels[peak_at]
    if peak < LOUD_DB:
        return False
    low = high = peak_at
    while low > 0 and levels[low - 1] >= peak - DROP_DB:
        low -= 1
    while high < len(levels) - 1 and levels[high + 1] >= peak - DROP_DB:
        high += 1
    return (high - low + 1) * step >= max(MIN_BURST, RATIO * speech)


def crowd_lines(
    segments: Iterable[Segment], levels: Sequence[float], step: float = STEP
) -> set[str]:
    """The ids of the lines that are crowd bursts."""
    return {s.id for s in segments if crowd_burst(s.start, s.end, levels, step)}
