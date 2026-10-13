"""Gemini connection: uploads a clip, asks a question about it, returns the structured answer.

Only vendor mechanics live here (upload, wait, retry, quota, token counts). What to ask and what
to do with the answer belongs to `velvetdub.features`.
"""

import time
from pathlib import Path

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel, ValidationError

from velvetdub.config.settings import Settings
from velvetdub.domain.usage import TokenUsage
from velvetdub.errors import ProviderError, QuotaExceededError
from velvetdub.providers.base import VideoAnalyzer
from velvetdub.providers.keys import require_key
from velvetdub.providers.registry import video_analyzers

UPLOAD_TIMEOUT_SECONDS = 600
POLL_SECONDS = 2.0
CONNECTION_ATTEMPTS = 4
CONNECTION_RETRY_SECONDS = 5.0
QUOTA_STATUS = 429
# The SDK's own retries cover temporary server trouble only. A 429 here is usually the daily limit,
# which no short wait fixes, so it must surface at once instead of burning more requests.
RETRY_STATUS_CODES = [408, 500, 502, 503, 504]


def retry_delay_seconds(details: object) -> int | None:
    """The service's 'retry in N seconds' hint from a quota error, if it gave one."""
    if not isinstance(details, dict):
        return None
    error = details.get("error")
    for item in error.get("details", []) if isinstance(error, dict) else []:
        delay = item.get("retryDelay") if isinstance(item, dict) else None
        if isinstance(delay, str) and delay.endswith("s"):
            try:
                return int(float(delay[:-1]))
            except ValueError:
                return None
    return None


def quota_error(error: genai_errors.APIError) -> QuotaExceededError:
    seconds = retry_delay_seconds(error.details)
    wait = ""
    if seconds is not None:
        hours, minutes = divmod(max(seconds, 60) // 60, 60)
        wait = (
            f" Try again in about {hours} h {minutes} min."
            if hours
            else (f" Try again in about {minutes} min.")
        )
    return QuotaExceededError(
        "Gemini's usage limit for this key is used up, so the scan stopped. Finished clips are "
        f"saved and the next run carries on from there.{wait} Turning on billing for the key's "
        "Google project raises the limit.",
        seconds,
    )


class GeminiVideoAnalyzer(VideoAnalyzer):
    name = "gemini"

    def __init__(self, client: genai.Client, model: str) -> None:
        super().__init__(model)
        self._client = client

    def analyze_clip[T: BaseModel](self, clip_path: Path, instructions: str, schema: type[T]) -> T:
        """The SDK retries bad HTTP statuses but not dropped connections, which long uploads and
        slow analyses hit now and then. One dropped connection must not cost the whole film."""
        self.last_usage = TokenUsage()
        for attempt in range(1, CONNECTION_ATTEMPTS + 1):
            try:
                return self._analyze_once(clip_path, instructions, schema)
            except httpx.TransportError:
                if attempt == CONNECTION_ATTEMPTS:
                    raise
                time.sleep(CONNECTION_RETRY_SECONDS * attempt)
            except genai_errors.APIError as error:
                if error.code == QUOTA_STATUS:
                    raise quota_error(error) from error
                raise
        raise AssertionError("unreachable")

    def _analyze_once[T: BaseModel](self, clip_path: Path, instructions: str, schema: type[T]) -> T:
        """The only method that talks to the network (tests replace it)."""
        uploaded = self._client.files.upload(file=clip_path)
        try:
            ready = self._wait_until_ready(uploaded.name or "")
            # Streamed, so data keeps arriving while the model works. A single long silent
            # request gets dropped ("Server disconnected") after about a minute and a half.
            answer: list[str] = []
            usage: types.GenerateContentResponseUsageMetadata | None = None
            block_reason: object = None
            for chunk in self._client.models.generate_content_stream(
                model=self.model or "",
                contents=[ready, instructions],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0.1,
                    # This is analysis of explicit material, not generation of it, so the
                    # service's own content blocking would only hide the very thing we look for.
                    safety_settings=[
                        types.SafetySetting(
                            category=category, threshold=types.HarmBlockThreshold.BLOCK_NONE
                        )
                        for category in (
                            types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        )
                    ],
                ),
            ):
                if chunk.text:
                    answer.append(chunk.text)
                if chunk.usage_metadata is not None:
                    usage = chunk.usage_metadata
                if chunk.prompt_feedback is not None and chunk.prompt_feedback.block_reason:
                    block_reason = chunk.prompt_feedback.block_reason
        finally:
            if uploaded.name:
                self._client.files.delete(name=uploaded.name)  # don't leave films on the service

        if usage is not None:
            self.last_usage = TokenUsage(
                input_tokens=usage.prompt_token_count or 0,
                output_tokens=(usage.candidates_token_count or 0)
                + (usage.thoughts_token_count or 0),
            )

        if block_reason:
            raise ProviderError(f"Gemini blocked this clip ({block_reason}).")
        try:
            return schema.model_validate_json("".join(answer))
        except ValidationError:
            raise ProviderError("Gemini returned no usable result for this clip.") from None

    def _wait_until_ready(self, name: str) -> types.File:
        deadline = time.monotonic() + UPLOAD_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            current = self._client.files.get(name=name)
            if current.state == types.FileState.ACTIVE:
                return current
            if current.state == types.FileState.FAILED:
                raise ProviderError("Gemini could not process the uploaded clip.")
            time.sleep(POLL_SECONDS)
        raise ProviderError("Timed out waiting for Gemini to process the clip.")


@video_analyzers.register("gemini")
def _create(settings: Settings) -> VideoAnalyzer:
    key = require_key(settings.gemini_api_key, "GEMINI_API_KEY")
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=4, http_status_codes=RETRY_STATUS_CODES)
        ),
    )
    return GeminiVideoAnalyzer(client, settings.moderation_model)
