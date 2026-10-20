"""Shapes the transcript into the lines a dub is spoken in: whole sentences, with the film's
pauses kept.

Subtitles want short lines; a dub wants the full sentence, or the voice reads half a thought and
then, much later, the other half. But a pause in the film is part of the performance: a line is
never joined across one, and a line that has one inside it is split there, so each part is spoken
when the actor says it and the silence stays silent."""

import re

from velvetdub.domain.transcript import Segment, Transcript, Word

# Bump this when the rules below change, so titles dubbed under the old rules are redone.
RULES_VERSION = "sentences-2"

# A line that ends like this is finished. A colon ends a line too: what follows is a new thought.
SENTENCE_ENDS = (".", "?", "!", "…", "。", "؟", "!", "?", ":")
PAUSE = 1.0  # seconds of silence that count as a pause: kept, never spoken through
MAX_SECONDS = 15.0  # no joined line is longer than this, so one line never runs on for a scene

# The transcription service sometimes stretches a word over the silence after it (a 2-letter word
# lasting 4 seconds), which hides the pause. A word is taken to last no longer than this.
_BASE_WORD = 0.3
_PER_LETTER = 0.1


def spoken_end(word: Word) -> float:
    """When the word really stops. A word cannot last much longer than its letters allow; any
    more than that is the silence after it, written down as part of the word."""
    letters = len(re.sub(r"\W", "", word.text)) or 1
    return min(word.end, word.start + _BASE_WORD + _PER_LETTER * letters)


def merge_sentences(transcript: Transcript) -> Transcript:
    """The same speech as whole sentences, numbered d0, d1, ... in order."""
    merged: list[Segment] = []
    for segment in _split_at_pauses(transcript.segments):
        if merged and _continues(merged[-1], segment):
            merged[-1] = _join(merged[-1], segment)
        else:
            merged.append(segment)
    renumbered = [segment.model_copy(update={"id": f"d{i}"}) for i, segment in enumerate(merged)]
    return Transcript(language=transcript.language, segments=renumbered)


def _split_at_pauses(segments: list[Segment]) -> list[Segment]:
    """Every line ends where its last word really stops, and a line with a pause inside it becomes
    one line per stretch of speech."""
    pieces: list[Segment] = []
    for segment in segments:
        if not segment.words:
            pieces.append(segment)
            continue
        runs: list[list[Word]] = [[segment.words[0]]]
        for before, after in zip(segment.words, segment.words[1:], strict=False):
            if after.start - spoken_end(before) >= PAUSE:
                runs.append([])
            runs[-1].append(after)
        if len(runs) == 1 and spoken_end(segment.words[-1]) >= segment.end:
            pieces.append(segment)  # nothing to change
            continue
        for run in runs:
            pieces.append(
                segment.model_copy(
                    update={
                        "start": run[0].start,
                        "end": max(run[0].start, spoken_end(run[-1])),
                        "text": " ".join(word.text for word in run),
                        "words": tuple(run),
                    }
                )
            )
    return pieces


def _continues(previous: Segment, current: Segment) -> bool:
    return (
        previous.speaker == current.speaker
        and not previous.text.rstrip().endswith(SENTENCE_ENDS)
        and current.start - previous.end < PAUSE
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
