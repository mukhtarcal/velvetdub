"""OpenAI Decisions connection: shows a few frames and gets back yes/no probabilities.

Only vendor mechanics live here (encoding, the call, rate limits, token counts). What to ask and
what to do with the answers belongs to `velvetdub.features`.
"""

import base64
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import openai

from velvetdub.config.settings import Settings
from velvetdub.domain.frames import FrameJudgement, FrameQuestion
from velvetdub.domain.usage import TokenUsage
from velvetdub.errors import ProviderError, QuotaExceededError
from velvetdub.providers.base import FrameJudge
from velvetdub.providers.keys import require_key
from velvetdub.providers.registry import frame_judges

MAX_RETRIES = 4  # the SDK retries rate limits and server errors with a growing wait


def _retry_seconds(error: openai.RateLimitError) -> int | None:
    value = error.response.headers.get("retry-after")
    try:
        return int(float(value)) if value is not None else None
    except ValueError:
        return None


class OpenAIFrameJudge(FrameJudge):
    name = "openai"

    def __init__(self, client: openai.OpenAI, model: str) -> None:
        super().__init__(model)
        self._client = client

    def judge(
        self, frames: Sequence[Path], intro: str, questions: Sequence[FrameQuestion]
    ) -> FrameJudgement:
        """The only method that talks to the network (tests replace the client)."""
        content: list[dict[str, str]] = [{"type": "input_text", "text": intro}]
        for frame in frames:
            data = base64.b64encode(frame.read_bytes()).decode("ascii")
            content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{data}"})
        asked = [
            {"type": "predicate", "name": q.name, "instructions": q.instructions} for q in questions
        ]
        try:
            decision = self._client.decisions.create(
                model=self.model or "",
                input=cast(Any, [{"role": "user", "content": content}]),
                questions=cast(Any, asked),
            )
        except openai.RateLimitError as error:
            seconds = _retry_seconds(error)
            wait = f" Try again in about {max(seconds, 1)} s." if seconds is not None else ""
            raise QuotaExceededError(
                "OpenAI's request limit or credit for this key is used up, so the scan stopped. "
                f"Finished clips are saved and the next run carries on from there.{wait} Check "
                "the usage and billing limits on the OpenAI account.",
                seconds,
            ) from error

        probabilities: dict[str, float] = {}
        for answer in decision.answers:
            if answer.type != "predicate":  # a refusal, or an answer we did not ask for
                raise ProviderError("OpenAI declined to judge some of these frames.")
            probabilities[answer.name or ""] = answer.probability
        usage = TokenUsage(
            input_tokens=decision.usage.input_tokens, output_tokens=decision.usage.output_tokens
        )
        return FrameJudgement(probabilities=probabilities, usage=usage)


@frame_judges.register("openai")
def _create(settings: Settings) -> FrameJudge:
    key = require_key(settings.openai_api_key, "OPENAI_API_KEY")
    return OpenAIFrameJudge(
        openai.OpenAI(api_key=key, max_retries=MAX_RETRIES), settings.moderation_model
    )
