"""Joining spoken lines into one dialogue track, with plain WAV handling (no ffmpeg).

Every line is a mono 16-bit WAV at `LINE_SAMPLE_RATE` (the synthesizer contract), so lines are
copied straight into the track a few seconds at a time and a long film never sits in memory."""

import sys
import wave
from array import array
from collections.abc import Iterable
from pathlib import Path

from velvetdub.domain.dubbing import LINE_SAMPLE_RATE, Placement

_SILENCE_CHUNK = 1.0  # seconds of silence written at a time

# Below this (of full scale) a sample counts as silence: about -34 dB.
SILENCE = 0.02
KEEP = 0.04  # seconds of quiet kept at each end, so a word is never clipped
FADE = 0.005  # seconds over which the cut ends are faded, so there is no click


def trim_silence(path: Path) -> tuple[float, bool]:
    """Cut the quiet off both ends of a spoken line, in place, and return (its new length in
    seconds, whether it had any sound at all). Voices pad a line with silence, so without this a
    line starts late and lasts longer than the word. Doing it again changes nothing, so it is
    safe on lines that were already trimmed.

    A voice service's WAV header can state the wrong length (or none: audio that was streamed),
    so the length is taken from the audio actually in the file, and a file whose header is wrong is
    written again with a correct one. The new file is made beside the old one and swapped in, so
    a failure part way never leaves a recording cut short."""
    with wave.open(str(path), "rb") as source:
        channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
        stated = source.getnframes()
        raw = source.readframes(stated)  # reads what is there, however long the header claims
    samples = array("h")
    samples.frombytes(raw[: len(raw) - len(raw) % (width * channels)])
    if sys.byteorder == "big":
        samples.byteswap()
    limit = int(SILENCE * 32767)
    loud = [i for i, value in enumerate(samples) if abs(value) > limit]
    if not loud:
        return len(samples) / rate, False
    keep = int(KEEP * rate)
    start, end = max(0, loud[0] - keep), min(len(samples), loud[-1] + keep + 1)
    if (start, end) == (0, len(samples)) and stated == len(samples):
        return len(samples) / rate, True
    trimmed = samples[start:end]
    fade = min(int(FADE * rate), len(trimmed) // 2)
    for i in range(fade):
        gain = i / fade
        trimmed[i] = int(trimmed[i] * gain)
        trimmed[-1 - i] = int(trimmed[-1 - i] * gain)
    if sys.byteorder == "big":
        trimmed.byteswap()
    partial = path.with_name(f"{path.stem}.trim.tmp.wav")
    try:
        with wave.open(str(partial), "wb") as out:
            out.setnchannels(channels)
            out.setsampwidth(width)
            out.setframerate(rate)
            out.writeframes(trimmed.tobytes())
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return len(trimmed) / rate, True


def wav_seconds(path: Path) -> float:
    """How long a WAV lasts. The header's count is only trusted as far as the file is long: audio
    that was streamed can state a length of hours, and a long stem must not be read to find out."""
    with wave.open(str(path), "rb") as source:
        frame = source.getnchannels() * source.getsampwidth()
        frames = min(source.getnframes(), path.stat().st_size // frame)
        return frames / source.getframerate()


def placed_starts(placements: Iterable[Placement]) -> list[float]:
    """Where each line really starts. A line never starts before the one ahead of it has
    finished, so a line that runs a little long pushes the next one back instead of overlapping
    it. Pace catches up in the next gap."""
    starts: list[float] = []
    cursor = 0.0
    for placement in sorted(placements, key=lambda p: p.start):
        start = max(placement.start, cursor)
        starts.append(start)
        cursor = start + wav_seconds(placement.path)
    return starts


def assemble_dialogue(placements: Iterable[Placement], dest: Path) -> None:
    """Write one mono WAV with each line at its start time, and silence between them."""
    ordered = sorted(placements, key=lambda p: p.start)
    starts = placed_starts(ordered)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(LINE_SAMPLE_RATE)
        written = 0  # frames
        for placement, start in zip(ordered, starts, strict=True):
            gap = max(0, round(start * LINE_SAMPLE_RATE) - written)
            chunk = round(_SILENCE_CHUNK * LINE_SAMPLE_RATE)
            while gap > 0:
                step = min(gap, chunk)
                out.writeframes(b"\x00\x00" * step)
                gap -= step
                written += step
            with wave.open(str(placement.path), "rb") as line:
                if (line.getnchannels(), line.getsampwidth(), line.getframerate()) != (
                    1,
                    2,
                    LINE_SAMPLE_RATE,
                ):
                    raise ValueError(
                        f"{placement.path.name} is not mono 16-bit {LINE_SAMPLE_RATE} Hz"
                    )
                frames = line.readframes(line.getnframes())
            out.writeframes(frames)
            written += len(frames) // 2
