import pytest

from velvetdub.domain.filtering import FilterCategory, Severity
from velvetdub.domain.transcript import Segment, Transcript, Word
from velvetdub.providers.wordlist import WordlistTextModerator


def flagged(text: str) -> list[tuple[str, Severity]]:
    tokens = text.split()
    words = tuple(Word(text=t, start=float(i), end=i + 0.5) for i, t in enumerate(tokens))
    transcript = Transcript(
        language="en",
        segments=[Segment(id="s0", start=0, end=len(tokens), text=text, speaker="A", words=words)],
    )
    events = WordlistTextModerator().scan_transcript(transcript)
    assert all(e.category is FilterCategory.SWEARING for e in events)
    return [(e.text or "", e.severity) for e in events]


@pytest.mark.parametrize(
    "word",
    ["fucker", "fuckin'", "Motherfucking", "unfuckable", "bullshit", "shitty", "Fuck!", "FUCK"],
)
def test_words_containing_a_strong_root_are_caught_whole(word: str) -> None:
    assert flagged(f"you {word} idiot") == [(word, Severity.STRONG)]


def test_the_longest_severity_wins_when_several_roots_match() -> None:
    assert flagged("motherfucker") == [("motherfucker", Severity.STRONG)]


@pytest.mark.parametrize("word", ["asshole", "bitches", "pissed", "goddamnit", "bastards"])
def test_moderate_roots_are_caught_inside_other_words(word: str) -> None:
    assert flagged(word) == [(word, Severity.MODERATE)]


@pytest.mark.parametrize(
    "word",
    ["class", "assume", "glass", "hello", "shell", "scrap", "cockpit", "peacock", "swank",
     "Atwater", "assassin", "Mississippi", "bassist", "passage", "Hancock", "title"],
)  # fmt: skip
def test_ordinary_words_are_left_alone(word: str) -> None:
    assert flagged(f"the {word} is here") == []


@pytest.mark.parametrize(
    ("word", "level"),
    [("hell", Severity.MILD), ("ass", Severity.MODERATE), ("dick", Severity.MODERATE),
     ("cock", Severity.MODERATE), ("crap", Severity.MILD), ("twat", Severity.STRONG)],
)  # fmt: skip
def test_short_words_match_only_as_whole_words(word: str, level: Severity) -> None:
    assert flagged(f"what the {word}.") == [(f"{word}.", level)]


def test_detector_identity_changes_with_the_word_list_version() -> None:
    assert WordlistTextModerator().identity.startswith("wordlist:v")
