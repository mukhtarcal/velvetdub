"""Picks the scanner for the provider named in MODERATION_PROVIDER."""

from velvetdub.config.settings import Settings
from velvetdub.errors import UnknownProviderError
from velvetdub.features.scene_filtering.scanner import FrameScanner, Scanner, SceneScanner
from velvetdub.providers import registry
from velvetdub.providers.provider_set import ProviderSet


def build_scene_scanner(providers: ProviderSet, settings: Settings) -> Scanner:
    name = settings.moderation_provider
    if name in registry.frame_judges.names():
        return FrameScanner(providers.frame_judge, settings.frame_threshold)
    if name in registry.video_analyzers.names():
        return SceneScanner(providers.video_analyzer)
    available = sorted({*registry.frame_judges.names(), *registry.video_analyzers.names()})
    raise UnknownProviderError(
        f"Unknown visual moderation provider '{name}'. Available: {', '.join(available)}"
    )
