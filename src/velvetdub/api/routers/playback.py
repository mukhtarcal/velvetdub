from fastapi import APIRouter
from pydantic import BaseModel, Field

from velvetdub.api.deps import ContainerDep, CurrentUser
from velvetdub.domain.overrides import Overrides
from velvetdub.services.playback import PlaybackInfo, ReviewInfo
from velvetdub.storage.corrections import Correction, CorrectionKind

router = APIRouter(tags=["playback"])


@router.get("/titles/{title_id}/playback")
def playback(title_id: str, container: ContainerDep, user: CurrentUser) -> PlaybackInfo:
    return container.playback.build(user.id, title_id)


@router.get("/titles/{title_id}/review")
def review(title_id: str, container: ContainerDep, user: CurrentUser) -> ReviewInfo:
    return container.playback.review(user.id, title_id)


class KeepRequest(BaseModel):
    event_ids: list[str] = Field(max_length=5000)
    keep: bool


@router.put("/titles/{title_id}/keep")
def keep_events(
    title_id: str, body: KeepRequest, container: ContainerDep, user: CurrentUser
) -> Overrides:
    """Keep in (or filter again) many detections at once, such as a whole category."""
    return container.overrides.keep_many(user.id, title_id, body.event_ids, keep=body.keep)


@router.put("/titles/{title_id}/events/{event_id}/keep")
def keep_event(
    title_id: str, event_id: str, container: ContainerDep, user: CurrentUser
) -> Overrides:
    """ "Keep it in": stop filtering this detection."""
    return container.overrides.keep(user.id, title_id, event_id, keep=True)


@router.delete("/titles/{title_id}/events/{event_id}/keep")
def unkeep_event(
    title_id: str, event_id: str, container: ContainerDep, user: CurrentUser
) -> Overrides:
    """Filter this detection again."""
    return container.overrides.keep(user.id, title_id, event_id, keep=False)


class CorrectionRequest(BaseModel):
    kind: CorrectionKind
    at_seconds: float
    category: str | None = None
    event_id: str | None = None
    note: str | None = None


@router.post("/titles/{title_id}/corrections", status_code=201)
def add_correction(
    title_id: str, body: CorrectionRequest, container: ContainerDep, user: CurrentUser
) -> Correction:
    container.store.get(user.id, title_id)  # must be your title
    return container.corrections.add(
        Correction(owner_id=user.id, title_id=title_id, **body.model_dump())
    )


@router.get("/titles/{title_id}/corrections")
def list_corrections(title_id: str, container: ContainerDep, user: CurrentUser) -> list[Correction]:
    container.store.get(user.id, title_id)
    return container.corrections.list(user.id, title_id)
