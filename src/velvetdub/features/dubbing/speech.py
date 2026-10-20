"""Speaks one line and fits it into the room it has."""

from dataclasses import dataclass
from pathlib import Path

from velvetdub.domain.dubbing import SynthesisRequest
from velvetdub.media.dialogue import trim_silence
from velvetdub.media.tools import MediaTool
from velvetdub.providers.base import SpeechSynthesizer

MARGIN = 1.02  # ask for a hair faster than needed, since the pace is only approximate
FIT_SLACK = 0.1  # seconds a line may run past its room and still count as fitting
STRETCH_FROM = 0.3  # seconds over, after speeding up, before the line is squeezed further
STRETCH_LIMIT = 1.2  # the most a finished line is squeezed (on top of any faster speaking)
MAX_TAKES = 4  # the most times one line is asked for
# A line that is this far over its room after two takes is not just a little long: the voice
# stretched it out (a one-word line can come back several seconds long, or as silence), so it
# is asked for again rather than squeezed.
RUNAWAY_FROM = 0.5  # seconds over, and also more than RUNAWAY_SHARE of the room
RUNAWAY_SHARE = 0.4


@dataclass
class Recorded:
    seconds: float  # how long the line lasts (silence at both ends trimmed)
    takes: int  # how many times the voice service was asked


@dataclass
class _Take:
    path: Path
    seconds: float
    usable: bool  # False if it came back silent


class LineRecorder:
    """Records a line at the voice's natural pace, takes the silence off both ends (so it starts on
    its word and lasts as long as the word), and if it is too long for its room asks for it faster,
    as far as the service allows.

    A voice model is erratic on very short lines: the same one-word line can come back as 0.3 s,
    as 5 s of drawn-out sound, or as silence. So when a line is far too long after two takes, or
    came back silent, it is asked for again (up to `MAX_TAKES`) and the best take is kept. As a last
    resort the recording is squeezed a little. A line that still runs long is kept: the dub pushes
    the next line back, not cuts it. Returns None if the voice never produced any sound."""

    def __init__(self, synthesizer: SpeechSynthesizer, media: MediaTool) -> None:
        self._synthesizer = synthesizer
        self._media = media

    def record(
        self, text: str, voice_id: str, language: str, slot: float, dest: Path
    ) -> Recorded | None:
        request = SynthesisRequest(text=text, voice_id=voice_id, language=language)
        takes: list[_Take] = []
        speed = 1.0
        while len(takes) < MAX_TAKES:
            path = dest.with_name(f"{dest.stem}.take{len(takes)}.wav")
            self._synthesizer.synthesize(request.model_copy(update={"speed": speed}), path)
            seconds, usable = trim_silence(path)
            takes.append(_Take(path, seconds, usable))
            best = _best(takes, slot)
            if best.usable and best.seconds <= slot + FIT_SLACK:
                break
            if len(takes) >= 2 and best.usable and not _runaway(best, slot):
                break  # a little long: squeezing it is enough
            if self._synthesizer.max_speed > 1.0 and best.usable:
                # Ask for it faster, by as much as it was too long.
                speed = min(self._synthesizer.max_speed, max(speed, best.seconds / slot * MARGIN))
            elif len(takes) == 2:
                speed = 1.0  # the faster take also failed: go back to the natural pace
        best = _best(takes, slot)
        for take in takes:
            if take is not best:
                take.path.unlink(missing_ok=True)
        if not best.usable:
            best.path.unlink(missing_ok=True)
            return None
        best.path.replace(dest)
        seconds = best.seconds
        if seconds > slot + STRETCH_FROM:
            squeezed = dest.with_name(f"{dest.stem}.squeezed.wav")
            self._media.change_tempo(dest, squeezed, min(STRETCH_LIMIT, seconds / slot))
            squeezed.replace(dest)
            seconds, _ = trim_silence(dest)
        return Recorded(seconds=seconds, takes=len(takes))


def _runaway(take: _Take, slot: float) -> bool:
    over = take.seconds - slot
    return over > max(RUNAWAY_FROM, RUNAWAY_SHARE * slot)


def _best(takes: list[_Take], slot: float) -> _Take:
    """The take that fits best: any with sound beats a silent one, then the least over its room."""
    return min(takes, key=lambda t: (not t.usable, max(0.0, t.seconds - slot), t.seconds))
