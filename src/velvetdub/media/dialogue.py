"""Joining spoken lines into one dialogue track, with plain WAV handling (no ffmpeg).

Every line is a mono 16-bit WAV at `LINE_SAMPLE_RATE` (the synthesizer contract), so lines are
copied straight into the track a few seconds at a time and a long film never sits in memory."""

import wave
from collections.abc import Iterable
from pathlib import Path

from velvetdub.domain.dubbing import LINE_SAMPLE_RATE, Placement

_SILENCE_CHUNK = 1.0  # seconds of silence written at a time


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as source:
        return source.getnframes() / source.getframerate()


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
