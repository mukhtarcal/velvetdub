"""Reading and writing WebVTT and SRT."""

import re

from velvetdub.errors import VelvetDubError
from velvetdub.subtitles.webvtt import Cue, format_webvtt

__all__ = ["Cue", "SubtitleParseError", "format_srt", "format_webvtt", "parse_cues"]

_TIME = re.compile(
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
)


class SubtitleParseError(VelvetDubError):
    """The file is not valid WebVTT or SRT."""


def _seconds(hours: str | None, minutes: str, seconds: str, fraction: str) -> float:
    millis = int(fraction.ljust(3, "0"))
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + millis / 1000


def parse_cues(text: str) -> list[Cue]:
    """Parse WebVTT or SRT (they share a cue layout), ignoring headers, notes and cue ids."""
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n").strip()):
        lines = block.split("\n")
        for index, line in enumerate(lines):
            match = _TIME.search(line)
            if match:
                g = match.groups()
                body = "\n".join(lines[index + 1 :]).strip()
                if body:
                    cues.append(
                        Cue(
                            start=_seconds(g[0], g[1], g[2], g[3]),
                            end=_seconds(g[4], g[5], g[6], g[7]),
                            text=body,
                        )
                    )
                break
    if not cues:
        raise SubtitleParseError("No subtitle lines were found in this file.")
    return cues


def _srt_timestamp(seconds: float) -> str:
    total_ms = round(max(seconds, 0.0) * 1000)
    hours, rest = divmod(total_ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def format_srt(cues: list[Cue]) -> str:
    blocks = [
        f"{i}\n{_srt_timestamp(c.start)} --> {_srt_timestamp(c.end)}\n{c.text}"
        for i, c in enumerate(cues, start=1)
    ]
    return "\n\n".join(blocks) + "\n"
