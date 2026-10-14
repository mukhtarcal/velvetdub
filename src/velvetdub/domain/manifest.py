"""The manifest is the index of everything known about one title."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from velvetdub.domain.filtering import FilterCategory


class StageStatus(StrEnum):
    DONE = "done"
    FAILED = "failed"


class StageRecord(BaseModel):
    status: StageStatus
    fingerprint: str = ""
    finished_at: datetime | None = None
    error: str | None = None


class TrackKind(StrEnum):
    ORIGINAL = "original"
    DUB = "dub"


class AudioTrack(BaseModel):
    """`path` is relative to the title folder. Phase 2 dubs are just more entries here."""

    id: str
    label: str
    language: str | None
    kind: TrackKind
    path: str


class SubtitleTrack(BaseModel):
    language: str
    path: str


class Choices(BaseModel):
    """What was asked for when processing last started, for the library's "what you chose" line."""

    filter_categories: list[FilterCategory] = Field(default_factory=list)
    subtitle_languages: list[str] = Field(default_factory=list)


def _now() -> datetime:
    return datetime.now(UTC)


class Manifest(BaseModel):
    schema_version: int = 1
    title_id: str
    owner_id: str
    name: str
    source_filename: str
    duration: float | None = None
    created_at: datetime = Field(default_factory=_now)
    stages: dict[str, StageRecord] = Field(default_factory=dict)
    audio_tracks: list[AudioTrack] = Field(default_factory=list)
    subtitle_tracks: list[SubtitleTrack] = Field(default_factory=list)
    choices: Choices | None = None
    # What the picture scan actually looked for (None until it has run). A detection list that is
    # empty means "nothing found" only for these categories.
    scanned_categories: list[FilterCategory] | None = None

    def upsert_audio_track(self, track: AudioTrack) -> None:
        self.audio_tracks = [t for t in self.audio_tracks if t.id != track.id] + [track]

    def upsert_subtitle_track(self, track: SubtitleTrack) -> None:
        self.subtitle_tracks = [t for t in self.subtitle_tracks if t.language != track.language]
        self.subtitle_tracks.append(track)
