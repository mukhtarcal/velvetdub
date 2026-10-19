"""What dubbing can do on this install."""

from velvetdub.errors import ConfigError
from velvetdub.providers.provider_set import ProviderSet


def dubbing_languages(providers: ProviderSet) -> list[str]:
    """The languages a dub can be made in, or none when this install can't dub yet (no voice
    service key, or the dubbing extras aren't installed). Needs no network."""
    try:
        providers.separator  # noqa: B018  (creating it is the check: it fails if not installed)
        synthesizer = providers.synthesizer
    except ConfigError:
        return []
    return sorted(synthesizer.languages()) if synthesizer.supports_cloning else []
