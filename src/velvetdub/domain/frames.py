"""Yes/no questions asked about a few frames of a film, and the answers that come back."""

from pydantic import BaseModel, ConfigDict, Field

from velvetdub.domain.usage import TokenUsage


class FrameQuestion(BaseModel):
    """A condition to judge, such as "does this show exposed nudity?". `name` is how the answer
    is looked up."""

    model_config = ConfigDict(frozen=True)

    name: str
    instructions: str


class FrameJudgement(BaseModel):
    """How likely (0 to 1) each question's condition is true for the frames shown."""

    model_config = ConfigDict(frozen=True)

    probabilities: dict[str, float]
    usage: TokenUsage = Field(default_factory=TokenUsage)
