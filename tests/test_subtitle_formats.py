import pytest

from velvetdub.domain.filtering import (
    FilterAction,
    FilterCategory,
    FilterEvent,
    ResolvedFilter,
    Severity,
)
from velvetdub.subtitles.formats import SubtitleParseError, format_srt, parse_cues
from velvetdub.subtitles.masking import mask_cues
from velvetdub.subtitles.webvtt import Cue, format_webvtt

VTT = """WEBVTT

NOTE a comment

intro
00:00:01.000 --> 00:00:02.500
Hello

00:01:00.250 --> 00:01:02.000
Second
line
"""

SRT = """1
00:00:01,000 --> 00:00:02,500
Hello

2
00:01:00,250 --> 00:01:02,000
Second
line
"""


@pytest.mark.parametrize("text", [VTT, SRT, SRT.replace("\n", "\r\n")])
def test_parses_vtt_and_srt(text: str) -> None:
    cues = parse_cues(text)
    assert [(c.start, c.end, c.text) for c in cues] == [
        (1.0, 2.5, "Hello"),
        (60.25, 62.0, "Second\nline"),
    ]


def test_hours_are_optional_in_vtt() -> None:
    (cue,) = parse_cues("WEBVTT\n\n01:05.500 --> 01:07.000\nHi\n")
    assert (cue.start, cue.end) == (65.5, 67.0)


def test_rejects_files_without_cues() -> None:
    with pytest.raises(SubtitleParseError):
        parse_cues("this is not a subtitle file")


def test_round_trips_through_both_formats() -> None:
    cues = [Cue(start=1, end=2, text="A"), Cue(start=3.5, end=4, text="B\nC")]
    assert parse_cues(format_webvtt(cues)) == cues
    assert parse_cues(format_srt(cues)) == cues


def event(text: str, start: float, end: float, action: FilterAction) -> ResolvedFilter:
    return ResolvedFilter(
        event=FilterEvent(
            id=f"e{start}",
            category=FilterCategory.SWEARING,
            severity=Severity.STRONG,
            start=start,
            end=end,
            source="t",
            text=text,
        ),
        action=action,
    )


def test_masks_muted_words_in_the_cue_they_were_spoken_in() -> None:
    cues = [Cue(start=0, end=2, text="What the hell, Hello."), Cue(start=10, end=12, text="hell")]
    out = mask_cues(cues, [event("hell,", 1.0, 1.3, FilterAction.MUTE)])
    assert out[0].text == "What the ****, Hello."  # whole word only; "Hello" is untouched
    assert out[1].text == "hell"  # a different moment, not masked


def test_skip_actions_do_not_mask_text() -> None:
    cues = [Cue(start=0, end=2, text="damn")]
    assert mask_cues(cues, [event("damn", 0, 1, FilterAction.SKIP)])[0].text == "damn"


def test_masking_is_case_insensitive_and_keeps_length() -> None:
    (cue,) = mask_cues(
        [Cue(start=0, end=2, text="DAMN it")], [event("Damn", 0, 1, FilterAction.MUTE)]
    )
    assert cue.text == "**** it"
