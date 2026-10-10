from pydantic import BaseModel, Field


class Overrides(BaseModel):
    """Detections the viewer chose to keep in ("Keep it in"), by event id."""

    keep: list[str] = Field(default_factory=list)
