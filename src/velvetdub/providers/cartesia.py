"""Cartesia connection: copies voices from a short recording and speaks text in them.

Only vendor mechanics live here (upload, call, retry, quota). What to say, how fast, and how a
line fits the film belongs to `velvetdub.features.dubbing`."""

import time
from collections.abc import Callable
from pathlib import Path

import httpx

from velvetdub.config.settings import Settings
from velvetdub.domain.dubbing import LINE_SAMPLE_RATE, SynthesisRequest, Voice
from velvetdub.errors import ProviderError, QuotaExceededError
from velvetdub.providers.base import SpeechSynthesizer
from velvetdub.providers.keys import require_key
from velvetdub.providers.registry import synthesizers

API = "https://api.cartesia.ai"
API_VERSION = "2026-08-14"
DEFAULT_MODEL = "sonic-3.6"
TIMEOUT_SECONDS = 180.0
ATTEMPTS = 4

# Languages the Sonic 3.x models speak.
_CODES = (
    "en de es fr ja pt zh hi ko it nl pl ru sv tr tl bg ro ar cs el fi hr ms sk da ta uk hu no "
    "vi bn th he ka id te gu kn ml mr pa or ur"
)
LANGUAGES = frozenset(_CODES.split())


class CartesiaSynthesizer(SpeechSynthesizer):
    name = "cartesia"
    supports_cloning = True
    max_speed = 1.5  # the service accepts 0.6 to 1.5

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        *,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(model)
        self._client = client or httpx.Client(timeout=TIMEOUT_SECONDS)
        self._headers = {"Authorization": f"Bearer {api_key}", "Cartesia-Version": API_VERSION}
        self._sleep = sleep

    def languages(self) -> frozenset[str]:
        return LANGUAGES

    def list_voices(self, language: str | None = None) -> list[Voice]:
        response = self._send("GET", "/voices", params={"limit": 100})
        voices = [
            Voice(id=v["id"], name=v.get("name", ""), language=v.get("language"))
            for v in response.json().get("data", [])
        ]
        return [v for v in voices if language is None or v.language == language]

    def clone_voice(self, sample: Path, name: str, language: str) -> Voice:
        with sample.open("rb") as clip:
            response = self._send(
                "POST",
                "/voices/clone",
                files={"clip": (sample.name, clip, "audio/wav")},
                data={"name": name, "language": language},
            )
        return Voice(id=response.json()["id"], name=name, language=language)

    def delete_voice(self, voice_id: str) -> None:
        self._send("DELETE", f"/voices/{voice_id}")

    def synthesize(self, request: SynthesisRequest, dest: Path) -> Path:
        body = {
            "model_id": self.model or DEFAULT_MODEL,
            "transcript": request.text,
            "voice": {"id": request.voice_id},
            "language": request.language,
            "output_format": {
                "container": "wav",
                "encoding": "pcm_s16le",
                "sample_rate": LINE_SAMPLE_RATE,
            },
            "generation_config": {"speed": round(min(request.speed, self.max_speed), 3)},
        }
        response = self._send("POST", "/tts/bytes", json=body)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return dest

    def _send(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        """One request, retried when the service is busy. Messages never include the key."""
        for attempt in range(1, ATTEMPTS + 1):
            try:
                response = self._client.request(
                    method,
                    f"{API}{path}",
                    headers=self._headers,
                    **kwargs,  # type: ignore[arg-type]
                )
            except httpx.TransportError as exc:
                if attempt == ATTEMPTS:
                    raise ProviderError("Could not reach Cartesia. Check the connection.") from exc
                self._sleep(2.0**attempt)
                continue
            if response.is_success:
                return response
            busy = response.status_code == 429 or response.status_code >= 500
            if busy and attempt < ATTEMPTS:
                self._sleep(2.0**attempt)
                continue
            raise _failure(response)
        raise AssertionError("unreachable")  # pragma: no cover


def _failure(response: httpx.Response) -> ProviderError:
    status = response.status_code
    if status in (401, 403):
        return ProviderError("Cartesia did not accept the key. Check CARTESIA_API_KEY in .env.")
    if status in (402, 429):
        return QuotaExceededError(
            "Cartesia's usage limit was reached. Saved lines are kept, so trying again later "
            "carries on where this stopped."
        )
    return ProviderError(f"Cartesia refused the request ({status}).")


@synthesizers.register("cartesia")
def _create(settings: Settings) -> SpeechSynthesizer:
    key = require_key(settings.cartesia_api_key, "CARTESIA_API_KEY")
    return CartesiaSynthesizer(key, settings.tts_model or DEFAULT_MODEL)
