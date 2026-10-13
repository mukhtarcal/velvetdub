"""The questions asked about each few-second window of frames.

One question per kind of moment we filter in this mode. A window of several consecutive frames
gets the "section of frames" wording; a lone frame (a very short clip) gets the single-frame one.
"""

from velvetdub.domain.frames import FrameQuestion

NUDITY = "nudity"
SEXUAL = "sexual"

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


def questions_for(frame_count: int) -> list[FrameQuestion]:
    many = frame_count > 1
    return [
        FrameQuestion(name=NUDITY, instructions=_NUDITY_MANY if many else _NUDITY_ONE),
        FrameQuestion(
            name=SEXUAL,
            instructions=("Could this section of frames " if many else "Could this film frame ")
            + _SEXUAL_TAIL,
        ),
    ]
