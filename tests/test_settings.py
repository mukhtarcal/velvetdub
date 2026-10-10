from pathlib import Path

import pytest
from pydantic import ValidationError

from velvetdub.config.settings import PROJECT_ROOT, Settings


def test_dotenv_beats_shell_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=from-dotenv\n")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-shell")

    settings = Settings(_env_file=env_file)

    assert settings.anthropic_api_key is not None
    assert settings.anthropic_api_key.get_secret_value() == "from-dotenv"


def test_blank_values_become_none_and_do_not_fall_back_to_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=\nTRANSCRIPTION_MODEL=\n")
    monkeypatch.setenv("GEMINI_API_KEY", "from-shell")

    settings = Settings(_env_file=env_file)

    assert settings.gemini_api_key is None
    assert settings.transcription_model is None


def test_blank_required_model_is_rejected(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("MODERATION_MODEL=\n")
    with pytest.raises(ValidationError):
        Settings(_env_file=env_file)


def test_relative_data_dir_resolves_against_project_root() -> None:
    settings = Settings(_env_file=None, data_dir=Path("data"))
    assert settings.data_path == PROJECT_ROOT / "data"
