"""Everything the player needs to start a title, resolved for one viewer's profile."""

from pydantic import BaseModel

from velvetdub.domain.filtering import (
    FilterPolicy,
    FilterTimeline,
    Region,
    ResolvedFilter,
)
from velvetdub.domain.manifest import TrackKind
from velvetdub.services.overrides import OverrideService
from velvetdub.storage.artifacts import read_model
from velvetdub.storage.profiles import ProfileRepository
from velvetdub.storage.title_store import TitleStore


class AudioTrackOut(BaseModel):
    id: str
    label: str
    language: str | None
    kind: TrackKind
    url: str


class SubtitleTrackOut(BaseModel):
    language: str
    url: str


class FilterOut(BaseModel):
    id: str
    category: str
    severity: str
    action: str
    start: float
    end: float
    text: str | None
    note: str | None
    confidence: float
    region: Region | None


class ProfileOut(BaseModel):
    id: str
    name: str


class ReviewFilterOut(FilterOut):
    kept: bool


class ReviewInfo(BaseModel):
    title_id: str
    name: str
    duration: float | None
    profile: ProfileOut
    filters: list[ReviewFilterOut]
    runtime_removed: float


class PlaybackInfo(BaseModel):
    title_id: str
    name: str
    duration: float | None
    source_url: str
    audio_tracks: list[AudioTrackOut]
    subtitle_tracks: list[SubtitleTrackOut]
    profile: ProfileOut
    filters: list[FilterOut]
    kept: list[str]
    runtime_removed: float


def _filter_out(resolved: ResolvedFilter) -> FilterOut:
    event = resolved.event
    return FilterOut(
        id=event.id,
        category=event.category.value,
        severity=event.severity.name.lower(),
        action=resolved.action.value,
        start=event.start,
        end=event.end,
        text=event.text,
        note=event.note,
        confidence=event.confidence,
        region=event.region,
    )


class PlaybackService:
    def __init__(
        self,
        store: TitleStore,
        profiles: ProfileRepository,
        overrides: OverrideService,
        policy: FilterPolicy,
    ) -> None:
        self._store = store
        self._profiles = profiles
        self._overrides = overrides
        self._policy = policy

    def resolved_filters(
        self, owner_id: str, title_id: str, profile_id: str, *, include_kept: bool = False
    ) -> list[ResolvedFilter]:
        manifest = self._store.get(owner_id, title_id)
        profile = self._profiles.get(owner_id, profile_id)
        path = self._store.paths(manifest).filters
        timeline = read_model(path, FilterTimeline) if path.exists() else FilterTimeline()
        resolved = self._policy.resolve(timeline, profile)
        if include_kept:
            return resolved
        kept = set(self._overrides.get(owner_id, title_id).keep)
        return [r for r in resolved if r.event.id not in kept]

    def build(self, owner_id: str, title_id: str, profile_id: str) -> PlaybackInfo:
        manifest = self._store.get(owner_id, title_id)
        profile = self._profiles.get(owner_id, profile_id)
        active = self.resolved_filters(owner_id, title_id, profile_id)
        base = f"/api/titles/{title_id}"
        return PlaybackInfo(
            title_id=title_id,
            name=manifest.name,
            duration=manifest.duration,
            source_url=f"{base}/media/source",
            audio_tracks=[
                AudioTrackOut(
                    id=t.id,
                    label=t.label,
                    language=t.language,
                    kind=t.kind,
                    url=f"{base}/media/audio/{t.id}",
                )
                for t in manifest.audio_tracks
            ],
            subtitle_tracks=[
                SubtitleTrackOut(
                    language=t.language,
                    url=f"{base}/subtitles/{t.language}.vtt?profile={profile.id}",
                )
                for t in manifest.subtitle_tracks
            ],
            profile=ProfileOut(id=profile.id, name=profile.name),
            filters=[_filter_out(r) for r in active],
            kept=self._overrides.get(owner_id, title_id).keep,
            runtime_removed=self._policy.runtime_removed(active),
        )

    def review(self, owner_id: str, title_id: str, profile_id: str) -> ReviewInfo:
        """Every detection the profile would act on, including ones the viewer kept in."""
        manifest = self._store.get(owner_id, title_id)
        profile = self._profiles.get(owner_id, profile_id)
        everything = self.resolved_filters(owner_id, title_id, profile_id, include_kept=True)
        kept = set(self._overrides.get(owner_id, title_id).keep)
        active = [r for r in everything if r.event.id not in kept]
        return ReviewInfo(
            title_id=title_id,
            name=manifest.name,
            duration=manifest.duration,
            profile=ProfileOut(id=profile.id, name=profile.name),
            filters=[
                ReviewFilterOut(**_filter_out(r).model_dump(), kept=r.event.id in kept)
                for r in everything
            ],
            runtime_removed=self._policy.runtime_removed(active),
        )
