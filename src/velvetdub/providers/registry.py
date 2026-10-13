"""Name -> factory registries, one per provider kind.

Adding a vendor: subclass the interface, then register a factory under a name. Selecting it is
then just `TRANSCRIPTION_PROVIDER=<name>` in `.env`.
"""

from collections.abc import Callable

from velvetdub.config.settings import Settings
from velvetdub.errors import UnknownProviderError
from velvetdub.providers.base import (
    FrameJudge,
    Provider,
    SourceSeparator,
    SpeechSynthesizer,
    TextGenerator,
    TextModerator,
    Transcriber,
    VideoAnalyzer,
)


class ProviderRegistry[P: Provider]:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._factories: dict[str, Callable[[Settings], P]] = {}

    def register(self, name: str) -> Callable[[Callable[[Settings], P]], Callable[[Settings], P]]:
        def decorator(factory: Callable[[Settings], P]) -> Callable[[Settings], P]:
            if name in self._factories:
                raise ValueError(f"{self.kind} provider '{name}' is already registered")
            self._factories[name] = factory
            return factory

        return decorator

    def create(self, name: str, settings: Settings) -> P:
        try:
            factory = self._factories[name]
        except KeyError:
            raise UnknownProviderError(
                f"Unknown {self.kind} provider '{name}'. Available: {', '.join(self.names())}"
            ) from None
        return factory(settings)

    def names(self) -> list[str]:
        return sorted(self._factories)


transcribers: ProviderRegistry[Transcriber] = ProviderRegistry("transcription")
text_generators: ProviderRegistry[TextGenerator] = ProviderRegistry("translation")
video_analyzers: ProviderRegistry[VideoAnalyzer] = ProviderRegistry("visual moderation")
frame_judges: ProviderRegistry[FrameJudge] = ProviderRegistry("visual moderation (frames)")
text_moderators: ProviderRegistry[TextModerator] = ProviderRegistry("text moderation")
separators: ProviderRegistry[SourceSeparator] = ProviderRegistry("source separation")
synthesizers: ProviderRegistry[SpeechSynthesizer] = ProviderRegistry("speech synthesis")
