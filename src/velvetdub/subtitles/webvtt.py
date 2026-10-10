"""WebVTT output. Formatting only; deciding what to show is the caller's job."""

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict


class Cue(BaseModel):
    model_config = ConfigDict(frozen=True)

    start: float
    end: float
    text: str


def format_timestamp(seconds: float) -> str:
    total_ms = round(max(seconds, 0.0) * 1000)
    hours, rest = divmod(total_ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def format_webvtt(cues: Iterable[Cue]) -> str:
    lines = ["WEBVTT", ""]
    for cue in cues:
        lines.append(f"{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}")
        lines.append(cue.text)
        lines.append("")
    return "\n".join(lines)
