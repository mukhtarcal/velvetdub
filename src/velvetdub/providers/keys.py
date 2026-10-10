from pydantic import SecretStr

from velvetdub.errors import ConfigError


def require_key(key: SecretStr | None, env_name: str) -> str:
    """Unwrap a secret, or fail with a message that says which variable to set."""
    if key is None:
        raise ConfigError(f"{env_name} is not set. Add it to your .env file.")
    return key.get_secret_value()
