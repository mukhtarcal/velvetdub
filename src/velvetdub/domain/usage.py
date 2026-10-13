"""Token counts reported by a model service, so the cost of a long film can be seen."""

from pydantic import BaseModel


class TokenUsage(BaseModel, frozen=True):
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )
