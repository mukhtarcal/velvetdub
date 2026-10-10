"""Turn a flat stream of timed words into subtitle-sized, speaker-pure segments.

Pure logic with no vendor types, so any transcriber can feed it and it is easy to test.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from velvetdub.domain.transcript import Segment, Word

SENTENCE_END = (".", "?", "!", "…")


@dataclass(frozen=True)
class RawWord:
    """One word as a vendor reported it, with times in seconds."""

    text: str
    start: float
    end: float
    speaker: str | None = None
    confidence: float | None = None


def build_segments(
    words: Sequence[RawWord],
    *,
    max_duration: float = 7.0,
    max_chars: int = 84,
    max_gap: float = 0.8,
    min_sentence_duration: float = 1.0,
) -> list[Segment]:
    """Group words into lines. A new line starts when the speaker changes, the speaker pauses
    for longer than `max_gap`, or the line would get too long to read comfortably. A line also
    ends at sentence punctuation once it has lasted `min_sentence_duration`."""
    segments: list[Segment] = []
    current: list[RawWord] = []

    def flush() -> None:
        if not current:
            return
        segments.append(
            Segment(
                id=f"s{len(segments)}",
                start=current[0].start,
                end=current[-1].end,
                text=" ".join(w.text for w in current),
                speaker=current[0].speaker,
                words=tuple(
                    Word(text=w.text, start=w.start, end=w.end, confidence=w.confidence)
                    for w in current
                ),
            )
        )
        current.clear()

    for word in words:
        if current:
            line_chars = sum(len(w.text) + 1 for w in current) + len(word.text)
            too_long = word.end - current[0].start > max_duration or line_chars > max_chars
            if (
                word.speaker != current[-1].speaker
                or word.start - current[-1].end > max_gap
                or too_long
            ):
                flush()
        current.append(word)
        if (
            word.text.endswith(SENTENCE_END)
            and current[-1].end - current[0].start >= min_sentence_duration
        ):
            flush()
    flush()
    return segments
