"""Offline profanity detector driven by word lists.

Two lists, because short words are risky to match inside other words:

* `ROOTS` are matched anywhere inside a spoken word, so "fucker", "fuckin'", "motherfucking" and
  "bullshit" are all caught without being listed one by one. Only strings that essentially never
  occur inside an innocent word belong here.
* `WORDS` are matched only as whole words, for the cases where a root would hit innocent words
  ("ass" is in "class", "cock" in "cockpit", "crap" in "scrap", "wank" in "swank").

A flagged word is muted whole. Anything smarter (an LLM, a bigger list) can replace this by
registering another TextModerator.
"""

import re

from velvetdub.config.settings import Settings
from velvetdub.domain.filtering import FilterCategory, FilterEvent, Severity
from velvetdub.domain.transcript import Transcript
from velvetdub.providers.base import TextModerator
from velvetdub.providers.registry import text_moderators

# Raise when the lists change: it is part of the detector's identity, so films re-run their
# (cheap, local) filter merge and pick up the new words.
WORDLIST_VERSION = 2

M, S, X = Severity.MILD, Severity.MODERATE, Severity.STRONG

# Matched inside any word. Keep these long or distinctive.
ROOTS: dict[str, Severity] = {
    # strong
    "fuck": X,
    "shit": X,
    "cunt": X,
    "whore": X,
    "slut": X,
    "cocksuck": X,
    "jizz": X,
    "nigger": X,
    "faggot": X,
    # moderate
    "bitch": S,
    "bastard": S,
    "asshole": S,
    "arsehole": S,
    "dickhead": S,
    "bollock": S,
    "pussy": S,
    "piss": S,
    "douche": S,
    "goddamn": S,
}

# Matched only as a whole word (after lowercasing and dropping punctuation).
WORDS: dict[str, Severity] = {
    # mild
    "damn": M,
    "damned": M,
    "damnit": M,
    "hell": M,
    "crap": M,
    "crappy": M,
    "badass": M,
    "bugger": M,
    "buggered": M,
    # moderate
    "ass": S,
    "asses": S,
    "arse": S,
    "arses": S,
    "dumbass": S,
    "jackass": S,
    "smartass": S,
    "fatass": S,
    "dick": S,
    "dicks": S,
    "cock": S,
    "cocks": S,
    "prick": S,
    "pricks": S,
    "tits": S,
    "titties": S,
    "wank": S,
    "wanker": S,
    "wankers": S,
    "wanking": S,
    "tosser": S,
    "skank": S,
    "cumming": S,
    "twat": X,  # as a root it would hit names like "Atwater"
    "twats": X,
    # strong: slurs
    "nigga": X,
    "niggas": X,
    "fag": X,
    "fags": X,
    "dyke": X,
}

DEFAULT_WORDS = WORDS  # kept for callers that passed or read the old single list

_NON_LETTERS = re.compile(r"[^a-z]")


class WordlistTextModerator(TextModerator):
    name = "wordlist"

    def __init__(
        self,
        words: dict[str, Severity] | None = None,
        roots: dict[str, Severity] | None = None,
    ) -> None:
        super().__init__(model=f"v{WORDLIST_VERSION}")
        self._words = words if words is not None else WORDS
        self._roots = roots if roots is not None else ROOTS

    def _severity(self, spoken: str) -> Severity | None:
        word = _NON_LETTERS.sub("", spoken.lower())
        if not word:
            return None
        found = [level for root, level in self._roots.items() if root in word]
        whole = self._words.get(word)
        if whole is not None:
            found.append(whole)
        return max(found) if found else None

    def scan_transcript(self, transcript: Transcript) -> list[FilterEvent]:
        events: list[FilterEvent] = []
        for segment in transcript.segments:
            for index, word in enumerate(segment.words):
                severity = self._severity(word.text)
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
