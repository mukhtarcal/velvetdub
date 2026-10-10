import pytest

from velvetdub.config.settings import Settings
from velvetdub.errors import ConfigError, UnknownProviderError
from velvetdub.providers import registry
from velvetdub.providers.provider_set import ProviderSet


def test_providers_are_chosen_by_name(settings: Settings) -> None:
    providers = ProviderSet(settings)
    assert providers.transcriber.identity == "fake:default"
    assert providers.text_moderator.name == "wordlist"


def test_unknown_provider_lists_the_options(settings: Settings) -> None:
    bad = settings.model_copy(update={"transcription_provider": "nope"})
    with pytest.raises(UnknownProviderError, match="assemblyai"):
        _ = ProviderSet(bad).transcriber


def test_missing_key_names_the_variable(settings: Settings) -> None:
    real = settings.model_copy(update={"transcription_provider": "assemblyai"})
    with pytest.raises(ConfigError, match="ASSEMBLYAI_API_KEY"):
        _ = ProviderSet(real).transcriber


def test_phase2_providers_are_optional(settings: Settings) -> None:
    with pytest.raises(ConfigError, match="TTS_PROVIDER"):
        _ = ProviderSet(settings).synthesizer


def test_duplicate_registration_is_rejected() -> None:
    with pytest.raises(ValueError, match="already registered"):
        registry.transcribers.register("fake")(lambda settings: None)  # type: ignore[arg-type,return-value]
