"""A volume curve written as a small WAV, so ffmpeg can apply it to a long stem in one pass.

The curve is 1.0 where the original sound plays as it is and each window's gain inside it, with
short ramps in the gaps either side (never inside a window) so nothing clicks."""

import sys
import wave
from array import array
from collections.abc import Sequence
from pathlib import Path

from velvetdub.domain.dubbing import AmbienceWindow

RATE = 1000  # readings per second; ffmpeg smooths this up to the audio rate
RAMP = 0.12  # seconds each side of a window over which the volume moves
_FULL = 32767


def write_gain_envelope(
    dest: Path, windows: Sequence[AmbienceWindow], total_seconds: float
) -> None:
    """Write a mono 16-bit WAV, `RATE` samples a second, as long as the film (plus a second)."""
    size = int((total_seconds + 1.0) * RATE)
    curve = array("f", [1.0]) * size
    ramp = int(RAMP * RATE)
    for window in windows:
        start = max(0, min(size, round(window.start * RATE)))
        end = max(start, min(size, round(window.end * RATE)))
        curve[start:end] = array("f", [window.gain]) * (end - start)
        drop = 1.0 - window.gain
        for step in range(1, ramp + 1):
            level = 1.0 - drop * (1 - step / (ramp + 1))  # 1 -> gain, just outside the window
            before, after = start - step, end + step - 1
            if before >= 0:
                curve[before] = min(curve[before], level)
            if after < size:
                curve[after] = min(curve[after], level)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(RATE)
        samples = array("h", (round(v * _FULL) for v in curve))
        if sys.byteorder == "big":
            samples.byteswap()  # WAV is little-endian
        out.writeframes(samples.tobytes())
