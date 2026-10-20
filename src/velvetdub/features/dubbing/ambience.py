"""What to keep of the original sound under a dub.

The voice separator puts every human sound into the "dialogue" stem: the actors, but also crowds
cheering, chanting and singing. The dub replaces that whole stem, so those sounds vanish. They
can't be told apart from the actors, but the film says when an actor is speaking, so:

* between the actors' lines the stem plays untouched, which brings back cheering, chants and
  singing; and
* under a line it stays silent. A quiet bed of it can be kept in a crowd scene (`bed`), but the
  crowd and the actor are one sound, so the bed also keeps his voice: it is off by default.
"""

from bisect import bisect_right
from collections.abc import Iterable, Sequence

from velvetdub.domain.dubbing import AmbienceWindow
from velvetdub.domain.export import Span
from velvetdub.domain.transcript import Segment

PAD = 0.15  # seconds kept clear either side of a line, so no word of the original leaks out
CROWD_DB = -33.0  # a gap this loud (per second, in the dialogue stem) means a crowd is making noise
LOOK = 3  # seconds either side of a line to listen for a crowd


def speech_windows(segments: Iterable[Segment]) -> list[Span]:
    """Where the original actors speak, padded, with overlapping stretches joined."""
    windows: list[Span] = []
    for segment in sorted(segments, key=lambda s: s.start):
        start, end = max(0.0, segment.start - PAD), segment.end + PAD
        if windows and start <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(windows[-1][1], end))
        else:
            windows.append((start, end))
    return windows


def plan_ambience(
    windows: Sequence[Span], levels: Sequence[float], bed: float
) -> tuple[AmbienceWindow, ...]:
    """The gain for each window. `levels` is the dialogue stem's loudness, one reading per
    second. A window gets the `bed` if the gaps just before or after it are loud (a crowd), and
    is otherwise silent."""
    starts = [w[0] for w in windows]

    def speaking(second: int) -> bool:
        index = bisect_right(starts, second + 0.5) - 1
        return index >= 0 and windows[index][0] <= second + 0.5 < windows[index][1]

    def crowd_near(start: float, end: float) -> bool:
        before = range(int(start) - LOOK, int(start))
        after = range(int(end) + 1, int(end) + 1 + LOOK)
        return any(
            0 <= second < len(levels) and levels[second] > CROWD_DB and not speaking(second)
            for second in (*before, *after)
        )

    return tuple(
        AmbienceWindow(start=a, end=b, gain=bed if crowd_near(a, b) else 0.0) for a, b in windows
    )
