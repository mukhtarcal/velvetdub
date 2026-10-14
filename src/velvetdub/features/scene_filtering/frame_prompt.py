"""The questions asked about each few-second window of frames.

One question per kind of moment we filter in this mode. A window of several consecutive frames
gets the "section of frames" wording; a lone frame (a very short clip) gets the single-frame one.
"""

from collections.abc import Iterable

from velvetdub.domain.filtering import FilterCategory
from velvetdub.domain.frames import FrameQuestion

NUDITY = "nudity"
SEXUAL = "sexual"

# The frame judge only knows these two. Scary scenes and violence need a scanner that watches video.
QUESTION_FOR_CATEGORY = {
    FilterCategory.NUDITY: NUDITY,
    FilterCategory.SEXUAL_CONTENT: SEXUAL,
}
FRAME_CATEGORIES = tuple(QUESTION_FOR_CATEGORY)

_NUDITY_MANY = (
    "Do any of these film frames show exposed nudity: bare breasts, buttocks or genitals? "
    "Underwear, swimwear and covered skin do not count."
)
_NUDITY_ONE = (
    "Does this film frame show exposed nudity: bare breasts, buttocks or genitals? "
    "Underwear, swimwear and covered skin do not count."
)
_SEXUAL_TAIL = (
    "reasonably be interpreted as showing or implying sexual activity? Consider what is shown "
    "and what is suggested by the framing, body positions, expressions and anything partly out "
    "of view. Count implied or suggestive-but-not-explicit sexual activity. Do not count "
    "ordinary affection such as a kiss, a hug or dancing."
)


def intro_for(frame_count: int) -> str:
    if frame_count == 1:
        return "A single frame from a film."
    return f"{frame_count} consecutive frames from a film, in order, one second apart."


def questions_for(frame_count: int, categories: Iterable[FilterCategory]) -> list[FrameQuestion]:
    """Only the questions for the chosen categories."""
    many = frame_count > 1
    chosen = set(categories)
    questions: list[FrameQuestion] = []
    if FilterCategory.NUDITY in chosen:
        questions.append(
            FrameQuestion(name=NUDITY, instructions=_NUDITY_MANY if many else _NUDITY_ONE)
        )
    if FilterCategory.SEXUAL_CONTENT in chosen:
        lead = "Could this section of frames " if many else "Could this film frame "
        questions.append(FrameQuestion(name=SEXUAL, instructions=lead + _SEXUAL_TAIL))
    return questions
