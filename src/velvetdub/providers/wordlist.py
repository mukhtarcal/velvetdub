"""Offline profanity detector driven by a small word list.

A starting point only; accuracy is tuned in step 1.1. Anything smarter (an LLM, a larger list)
can replace it by registering another TextModerator.
"""

import re

from velvetdub.config.settings import Settings
from velvetdub.domain.filtering import FilterCategory, FilterEvent, Severity
from velvetdub.domain.transcript import Transcript
from velvetdub.providers.base import TextModerator
from velvetdub.providers.registry import text_moderators

DEFAULT_WORDS: dict[str, Severity] = {
    "damn": Severity.MILD,
    "hell": Severity.MILD,
    "crap": Severity.MILD,
    "ass": Severity.MODERATE,
    "bastard": Severity.MODERATE,
    "shit": Severity.STRONG,
    "fuck": Severity.STRONG,
    "fucking": Severity.STRONG,
}

_NON_LETTERS = re.compile(r"[^a-z']")


class WordlistTextModerator(TextModerator):
    name = "wordlist"

    def __init__(self, words: dict[str, Severity] | None = None) -> None:
        super().__init__(model=None)
        self._words = words if words is not None else DEFAULT_WORDS

    def scan_transcript(self, transcript: Transcript) -> list[FilterEvent]:
        events: list[FilterEvent] = []
        for segment in transcript.segments:
            for index, word in enumerate(segment.words):
                severity = self._words.get(_NON_LETTERS.sub("", word.text.lower()))
                if severity is None:
                    continue
                events.append(
                    FilterEvent(
                        id=f"txt-{segment.id}-{index}",
                        category=FilterCategory.SWEARING,
                        severity=severity,
                        start=word.start,
                        end=word.end,
                        source=self.identity,
                        text=word.text,
                    )
                )
        return events


@text_moderators.register("wordlist")
def _create(settings: Settings) -> TextModerator:
    return WordlistTextModerator()
