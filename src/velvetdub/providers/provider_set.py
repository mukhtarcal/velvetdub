"""Resolves the providers chosen in settings, lazily.

Lazy so that a missing Phase 2 key never blocks Phase 1, and so a command only needs the keys
for the providers it actually uses.
"""

from functools import cached_property

import velvetdub.providers.anthropic
import velvetdub.providers.assemblyai
import velvetdub.providers.fake
import velvetdub.providers.gemini
import velvetdub.providers.openai_decisions
import velvetdub.providers.wordlist  # noqa: F401  (imports register the providers)
from velvetdub.config.settings import Settings
from velvetdub.errors import ConfigError
from velvetdub.providers import registry
from velvetdub.providers.base import (
    FrameJudge,
    SourceSeparator,
    SpeechSynthesizer,
    TextGenerator,
    TextModerator,
    Transcriber,
    VideoAnalyzer,
)


class ProviderSet:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    @cached_property
    def transcriber(self) -> Transcriber:
        return registry.transcribers.create(self._settings.transcription_provider, self._settings)

    @cached_property
    def text_generator(self) -> TextGenerator:
        """The model that translates (chosen by TRANSLATION_PROVIDER / TRANSLATION_MODEL)."""
        return registry.text_generators.create(self._settings.translation_provider, self._settings)

    @cached_property
    def video_analyzer(self) -> VideoAnalyzer:
        """The model that watches clips (chosen by MODERATION_PROVIDER / MODERATION_MODEL)."""
        return registry.video_analyzers.create(self._settings.moderation_provider, self._settings)

    @cached_property
    def frame_judge(self) -> FrameJudge:
        """The model that judges frames (chosen by MODERATION_PROVIDER / MODERATION_MODEL)."""
        return registry.frame_judges.create(self._settings.moderation_provider, self._settings)

    @cached_property
    def text_moderator(self) -> TextModerator:
        return registry.text_moderators.create(
            self._settings.text_moderation_provider, self._settings
        )

    @cached_property
    def separator(self) -> SourceSeparator:
        name = self._settings.separation_provider
        if not name:
            raise ConfigError("SEPARATION_PROVIDER is not set (needed for dubbing).")
        return registry.separators.create(name, self._settings)

    @cached_property
    def synthesizer(self) -> SpeechSynthesizer:
        name = self._settings.tts_provider
        if not name:
            raise ConfigError("TTS_PROVIDER is not set (needed for dubbing).")
        return registry.synthesizers.create(name, self._settings)
