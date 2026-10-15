"""Planning a "smart cut": making a cleaned copy without re-encoding the whole film.

Video can only be copied as is from one keyframe to the next. So for each piece of the film to
keep, whole stretches between keyframes are copied (fast, and bit-for-bit the original), and only
the partial stretch at each end, from the cut to the nearest keyframe, is encoded again. For a
film with a few dozen cuts that is a few percent of the picture instead of all of it.

Everything here is arithmetic on frame numbers, so it can be tested without any video."""

import math
from collections.abc import Iterable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from velvetdub.domain.export import Span

# Cut times come from detections, not from frames. A time within this fraction of a frame of a
# frame boundary counts as being on it, so float noise never moves a cut by a whole frame.
_FRAME_FUZZ = 1e-6


class VideoTiming(BaseModel):
    """How the picture is laid out in time: constant frame rate, frame 0 at `start`."""

    model_config = ConfigDict(frozen=True)

    start: float  # presentation time of the first frame, in seconds
    frame_duration: float
    frame_count: int

    def time_of(self, frame: int) -> float:
        return self.start + frame * self.frame_duration

    def frame_at_or_after(self, seconds: float) -> int:
        """The first frame shown at or after this time (0 to frame_count)."""
        index = math.ceil((seconds - self.start) / self.frame_duration - _FRAME_FUZZ)
        return min(max(index, 0), self.frame_count)


class Piece(BaseModel):
    """`frames` frames from `first_frame` of the source, copied as they are or encoded again."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["copy", "encode"]
    first_frame: int
    frames: int


def frame_ranges(keep: Iterable[Span], timing: VideoTiming) -> list[tuple[int, int]]:
    """The pieces to keep as `[first, end)` frame numbers, in order, without empty ones."""
    ranges: list[tuple[int, int]] = []
    for start, end in keep:
        first, stop = timing.frame_at_or_after(start), timing.frame_at_or_after(end)
        if stop > first:
            ranges.append((first, stop))
    return ranges


def audio_spans(ranges: Sequence[tuple[int, int]], timing: VideoTiming) -> list[Span]:
    """The same pieces as times, so the sound keeps exactly the stretches the picture does. A span
    runs from the first frame's time up to, but not including, the time of the frame after."""
    return [(timing.time_of(first), timing.time_of(stop)) for first, stop in ranges]


def plan_pieces(
    ranges: Sequence[tuple[int, int]], keyframes: Sequence[int], frame_count: int
) -> list[Piece]:
    """Split each range into encoded ends and a copied middle.

    `keyframes` are the frame numbers where decoding can start, in order. The middle runs from
    the first keyframe inside the range to the last one in it, so it holds only whole groups of
    pictures. A range with no whole group inside is encoded entirely. The film's last range may
    be copied to the very end, since nothing follows to cut it off from."""
    pieces: list[Piece] = []
    for first, stop in ranges:
        copy_from = next((k for k in keyframes if k >= first), None)
        copy_to: int | None
        if stop >= frame_count:
            copy_to = stop
        else:
            copy_to = max((k for k in keyframes if k <= stop), default=None)
        if copy_from is None or copy_to is None or copy_from >= copy_to:
            pieces.append(Piece(kind="encode", first_frame=first, frames=stop - first))
            continue
        if copy_from > first:
            pieces.append(Piece(kind="encode", first_frame=first, frames=copy_from - first))
        pieces.append(Piece(kind="copy", first_frame=copy_from, frames=copy_to - copy_from))
        if stop > copy_to:
            pieces.append(Piece(kind="encode", first_frame=copy_to, frames=stop - copy_to))
    return pieces
