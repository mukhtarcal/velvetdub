"""Joins the transcript's pause-sized lines into whole sentences before they are translated.

Subtitles want short lines; a dub wants the full sentence, or the voice reads half a thought and
then, much later, the other half."""

from velvetdub.domain.transcript import Segment, Transcript

# A line that ends like this is finished. A colon ends a line too: what follows is a new thought.
SENTENCE_ENDS = (".", "?", "!", "…", "。", "؟", "!", "?", ":")
MAX_PAUSE = 3.0  # an unfinished line joins the next one if the same person carries on within this
MAX_SECONDS = 15.0  # no joined line is longer than this, so one line never runs on for a scene


def merge_sentences(transcript: Transcript) -> Transcript:
    """The same speech as whole sentences, numbered d0, d1, ... in order."""
    merged: list[Segment] = []
    for segment in transcript.segments:
        if merged and _continues(merged[-1], segment):
            merged[-1] = _join(merged[-1], segment)
        else:
            merged.append(segment)
    renumbered = [segment.model_copy(update={"id": f"d{i}"}) for i, segment in enumerate(merged)]
    return Transcript(language=transcript.language, segments=renumbered)


def _continues(previous: Segment, current: Segment) -> bool:
    return (
        previous.speaker == current.speaker
        and not previous.text.rstrip().endswith(SENTENCE_ENDS)
        and current.start - previous.end <= MAX_PAUSE
        and current.end - previous.start <= MAX_SECONDS
    )


def _join(previous: Segment, current: Segment) -> Segment:
    return previous.model_copy(
        update={
            "end": current.end,
            "text": f"{previous.text.rstrip()} {current.text.lstrip()}",
            "words": previous.words + current.words,
        }
    )
