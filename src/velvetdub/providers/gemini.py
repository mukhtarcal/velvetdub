"""Gemini visual moderation: sends one short clip at a time and gets back timed detections."""

import time
from enum import StrEnum
from pathlib import Path
from typing import Literal

from google import genai
from google.genai import types
from pydantic import BaseModel

from velvetdub.config.settings import Settings
from velvetdub.domain.filtering import FilterCategory, FilterEvent, Severity
from velvetdub.errors import ProviderError
from velvetdub.providers.base import Moderator
from velvetdub.providers.keys import require_key
from velvetdub.providers.registry import moderators

UPLOAD_TIMEOUT_SECONDS = 600
POLL_SECONDS = 2.0

PROMPT = """You are reviewing a clip from a film or TV episode so that families can skip parts
they would rather not watch. List every moment that contains any of these:

- nudity: partial or full nudity
- sexual_content: kissing that turns sexual, sex scenes, strong sexual innuendo shown on screen
- violence: fights, weapons used on people, blood, injury, gore
- drugs_and_drinking: drug use, smoking, drinking alcohol
- scary_scenes: jump scares, frightening or disturbing imagery

For each moment give its start and end as MM:SS from the START OF THIS CLIP (not the film), a
severity (mild, moderate or strong), a confidence from 0 to 1, and a short neutral description.
Cover the whole moment, from when it begins to when it clearly ends.

Be conservative: a missed moment is worse than an extra one, so include anything doubtful with a
lower confidence. Judge only what you can see. Do not report swearing; spoken words are handled
elsewhere. If the clip has none of these, return an empty list."""


class VisualCategory(StrEnum):
    NUDITY = "nudity"
    SEXUAL_CONTENT = "sexual_content"
    VIOLENCE = "violence"
    DRUGS_AND_DRINKING = "drugs_and_drinking"
    SCARY_SCENES = "scary_scenes"


class Detection(BaseModel):
    start: str
    end: str
    category: VisualCategory
    severity: Literal["mild", "moderate", "strong"]
    confidence: float
    description: str


class ClipResult(BaseModel):
    detections: list[Detection]


SEVERITY = {"mild": Severity.MILD, "moderate": Severity.MODERATE, "strong": Severity.STRONG}


def parse_clock(value: str) -> float:
    """'MM:SS', 'H:MM:SS' or plain seconds -> seconds."""
    try:
        seconds = 0.0
        for part in value.strip().split(":"):
            seconds = seconds * 60 + float(part)
        return seconds
    except ValueError:
        raise ProviderError(f"Could not read timestamp '{value}' from the moderator.") from None


class GeminiModerator(Moderator):
    name = "gemini"

    def __init__(self, client: genai.Client, model: str) -> None:
        super().__init__(model)
        self._client = client

    def scan_clip(self, clip_path: Path, *, offset: float) -> list[FilterEvent]:
        result = self._analyse_clip(clip_path)
        events: list[FilterEvent] = []
        for index, found in enumerate(result.detections):
            start = offset + parse_clock(found.start)
            end = offset + parse_clock(found.end)
            events.append(
                FilterEvent(
                    id=f"vis-{offset:.0f}-{index}",
                    category=FilterCategory(found.category.value),
                    severity=SEVERITY[found.severity],
                    start=start,
                    end=max(start, end),
                    confidence=min(max(found.confidence, 0.0), 1.0),
                    source=self.identity,
                    note=found.description,
                )
            )
        return events

    def _analyse_clip(self, clip_path: Path) -> ClipResult:
        """The only method that talks to the network (tests replace it)."""
        uploaded = self._client.files.upload(file=clip_path)
        try:
            ready = self._wait_until_ready(uploaded.name or "")
            response = self._client.models.generate_content(
                model=self.model or "",
                contents=[ready, PROMPT],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ClipResult,
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
            )
        finally:
            if uploaded.name:
                self._client.files.delete(name=uploaded.name)  # don't leave films on the service

        parsed = response.parsed
        if isinstance(parsed, ClipResult):
            return parsed
        feedback = response.prompt_feedback
        if feedback is not None and feedback.block_reason:
            raise ProviderError(f"Gemini blocked this clip ({feedback.block_reason}).")
        raise ProviderError("Gemini returned no usable result for this clip.")

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


@moderators.register("gemini")
def _create(settings: Settings) -> Moderator:
    key = require_key(settings.gemini_api_key, "GEMINI_API_KEY")
    client = genai.Client(
        api_key=key,
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=4)),
    )
    return GeminiModerator(client, settings.moderation_model)
