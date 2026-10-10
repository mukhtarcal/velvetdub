"""Phase 2 value types. Defined now so the provider interfaces are stable."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Voice(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    language: str | None = None


class SynthesisRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    voice_id: str
    language: str
    target_duration: float | None = None


class SeparatedStems(BaseModel):
    model_config = ConfigDict(frozen=True)

    dialogue: Path
    background: Path
