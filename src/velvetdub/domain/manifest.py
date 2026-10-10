"""The manifest is the index of everything known about one title."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


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

    def upsert_audio_track(self, track: AudioTrack) -> None:
        self.audio_tracks = [t for t in self.audio_tracks if t.id != track.id] + [track]

    def upsert_subtitle_track(self, track: SubtitleTrack) -> None:
        self.subtitle_tracks = [t for t in self.subtitle_tracks if t.language != track.language]
        self.subtitle_tracks.append(track)
