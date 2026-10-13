"""Exception hierarchy. Every error the app raises on purpose derives from VelvetDubError."""


class VelvetDubError(Exception):
    """Base class for expected, user-reportable errors."""


class ConfigError(VelvetDubError):
    """Missing or invalid configuration (settings, API keys, unknown provider)."""


class UnknownProviderError(ConfigError):
    """A provider name in the settings is not registered."""


class TitleNotFoundError(VelvetDubError):
    """The title does not exist, or the caller does not own it."""


class MissingInputError(VelvetDubError):
    """A pipeline stage ran without the files it needs."""


class StageFailedError(VelvetDubError):
    """A pipeline stage raised; the original error is chained as __cause__."""

    def __init__(self, stage: str) -> None:
        super().__init__(f"Stage '{stage}' failed")
        self.stage = stage


class ToolNotFoundError(VelvetDubError):
    """A required external program (such as ffmpeg) is not installed."""


class ProviderError(VelvetDubError):
    """An external service failed, refused, or returned something unusable."""


class QuotaExceededError(ProviderError):
    """The service's usage limit is used up. Saved progress is kept, so trying again later
    carries on where this stopped."""

    def __init__(self, message: str, retry_after_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class InvalidNameError(VelvetDubError):
    """A language code, track id or similar name that is not safe to use in a file name."""
