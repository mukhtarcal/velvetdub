"""Picks the scanner for the provider named in MODERATION_PROVIDER."""

from collections.abc import Sequence

from velvetdub.config.settings import Settings
from velvetdub.domain.filtering import FilterCategory
from velvetdub.errors import UnknownProviderError
from velvetdub.features.scene_filtering.categories import PICTURE_CATEGORIES
from velvetdub.features.scene_filtering.frame_prompt import FRAME_CATEGORIES
from velvetdub.features.scene_filtering.scanner import FrameScanner, Scanner, SceneScanner
from velvetdub.providers import registry
from velvetdub.providers.provider_set import ProviderSet


def _unknown(name: str) -> UnknownProviderError:
    available = sorted({*registry.frame_judges.names(), *registry.video_analyzers.names()})
    return UnknownProviderError(
        f"Unknown visual moderation provider '{name}'. Available: {', '.join(available)}"
    )


def build_scene_scanner(
    providers: ProviderSet, settings: Settings, categories: Sequence[FilterCategory]
) -> Scanner:
    name = settings.moderation_provider
    if name in registry.frame_judges.names():
        return FrameScanner(providers.frame_judge, settings.frame_threshold, categories)
    if name in registry.video_analyzers.names():
        return SceneScanner(providers.video_analyzer, categories)
    raise _unknown(name)


def scannable_categories(settings: Settings) -> tuple[FilterCategory, ...]:
    """What the chosen scanner can look for. Needs no API key, so the UI can ask before anything
    is uploaded."""
    name = settings.moderation_provider
    if name in registry.frame_judges.names():
        return FRAME_CATEGORIES
    if name in registry.video_analyzers.names():
        return PICTURE_CATEGORIES
    raise _unknown(name)
