"""Application settings.

Precedence: explicit arguments > project `.env` > shell environment > defaults.
The project `.env` deliberately beats the shell, because the shell may hold work credentials.

Providers and models are chosen here by name only. Swapping one is a config change.
"""

from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Secrets
    anthropic_api_key: SecretStr | None = None
    assemblyai_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    elevenlabs_api_key: SecretStr | None = None
    cartesia_api_key: SecretStr | None = None

    # Storage
    data_dir: Path = Path("data")

    # Hostnames the local API answers to (blocks DNS-rebinding from web pages)
    allowed_hosts: list[str] = ["127.0.0.1", "localhost"]
    # The web app's own addresses. The browser sends a film straight to the API (a proxy would
    # hold the whole film in memory), which is a cross-origin request, so only these are approved.
    web_origins: list[str] = ["http://127.0.0.1:5273", "http://localhost:5273"]

    # Phase 1 providers (names must be registered in velvetdub.providers)
    transcription_provider: str = "assemblyai"
    transcription_model: str | None = None
    translation_provider: str = "anthropic"
    translation_model: str = "claude-sonnet-5-5"
    moderation_provider: str = "gemini"
    moderation_model: str = "gemini-3.8-flash"
    text_moderation_provider: str = "wordlist"
    visual_sample_fps: float = 1.0
    scan_clip_seconds: int = 600
    scan_height: int = 360
    # Frame-by-frame scan (OpenAI): a window counts as nudity/sexual content at or above this
    # chance. Lower is more sensitive and catches subtler scenes, at the cost of false alarms.
    frame_threshold: float = Field(default=0.5, gt=0, le=1)

    # Dubbing providers. Created only when a dub is asked for, so a missing Cartesia key or the
    # optional dubbing install never blocks subtitles and filters.
    tts_provider: str = "cartesia"
    tts_model: str | None = None  # None = the provider's own default model
    tts_concurrency: int = Field(default=4, ge=1, le=16)  # lines spoken at the same time
    separation_provider: str = "demucs"
    separation_model: str | None = None
    # The separator calls crowds, chanting and singing "dialogue", so a dub would lose them. This
    # keeps the original sound wherever no actor is speaking (see features/dubbing/ambience.py).
    dub_keep_crowd: bool = True
    # Under a line, in a crowd scene only: how much of the original dialogue stem stays, as a
    # quiet bed (0 = none, 1 = untouched). Off by default: the crowd and the actor are one sound
    # and cannot be pulled apart, so any bed also keeps the actor's own voice, and at 0.2 a speech
    # recogniser could still pick out his words behind the dub (measured on the Wolf of Wall
    # Street test; cutting the speech band out of the bed did not help).
    dub_crowd_bed: float = Field(default=0.0, ge=0, le=1)

    @field_validator(
        "anthropic_api_key",
        "assemblyai_api_key",
        "gemini_api_key",
        "openai_api_key",
        "elevenlabs_api_key",
        "cartesia_api_key",
        "transcription_model",
        "tts_model",
        "separation_model",
        mode="before",
    )
    @classmethod
    def _blank_is_none(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "transcription_provider",
        "translation_provider",
        "translation_model",
        "moderation_provider",
        "moderation_model",
        "text_moderation_provider",
        "tts_provider",
        "separation_provider",
    )
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()

    @property
    def data_path(self) -> Path:
        """Absolute data directory (relative values resolve against the project root)."""
        return self.data_dir if self.data_dir.is_absolute() else PROJECT_ROOT / self.data_dir

    @property
    def model_cache_path(self) -> Path:
        """Where downloaded model weights live: inside the project, never in ~/.cache."""
        return self.data_path / "cache"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, dotenv_settings, env_settings, file_secret_settings
