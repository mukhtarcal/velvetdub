import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from velvetdub.api.deps import ContainerDep, CurrentUser
from velvetdub.domain.filtering import FilterCategory
from velvetdub.domain.languages import language_name
from velvetdub.domain.manifest import Choices, Manifest
from velvetdub.features.dubbing.support import dubbing_languages
from velvetdub.features.scene_filtering.categories import PICTURE_CATEGORIES
from velvetdub.features.scene_filtering.factory import scannable_categories
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.services.jobs import JobState

router = APIRouter(prefix="/titles", tags=["titles"])

VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi"}
MAX_NAME_LENGTH = 200


class TitleSummary(BaseModel):
    id: str
    name: str
    created_at: datetime
    duration: float | None
    stages: dict[str, str]
    choices: Choices | None
    scanned_categories: list[FilterCategory] | None


class ProcessRequest(BaseModel):
    """Every list may be empty. Only what is chosen is run: with nothing chosen the film is just
    stored. `filter_categories` takes the four picture categories and swearing."""

    subtitle_languages: list[str] = Field(default_factory=list)
    filter_categories: list[FilterCategory] = Field(default_factory=list)
    dub_languages: list[str] = Field(default_factory=list)
    source_language: str | None = None

    @field_validator("filter_categories")
    @classmethod
    def _offered_filters_only(cls, value: list[FilterCategory]) -> list[FilterCategory]:
        # The four picture categories and swearing; the rest are not offered yet.
        for category in value:
            if category not in (*PICTURE_CATEGORIES, FilterCategory.SWEARING):
                raise ValueError(f"'{category.value}' is not something that can be chosen.")
        return value


def _summary(manifest: Manifest) -> TitleSummary:
    return TitleSummary(
        id=manifest.title_id,
        name=manifest.name,
        created_at=manifest.created_at,
        duration=manifest.duration,
        stages={name: record.status.value for name, record in manifest.stages.items()},
        choices=manifest.choices,
        scanned_categories=manifest.scanned_categories,
    )


@router.get("")
def list_titles(container: ContainerDep, user: CurrentUser) -> list[TitleSummary]:
    return [_summary(m) for m in container.store.list(user.id)]


@router.get("/{title_id}")
def get_title(title_id: str, container: ContainerDep, user: CurrentUser) -> Manifest:
    return container.store.get(user.id, title_id)


@router.post("", status_code=201)
async def upload_title(
    request: Request,
    container: ContainerDep,
    user: CurrentUser,
    name: str = Query(min_length=1, max_length=MAX_NAME_LENGTH),
    filename: str = Query(min_length=1, max_length=255),
) -> TitleSummary:
    """Upload a film as the raw request body, streamed to disk (never held in memory)."""
    suffix = Path(filename).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="That file type isn't a supported video.")

    staging = container.settings.data_path / "uploads"
    staging.mkdir(parents=True, exist_ok=True)
    target = staging / f"{uuid.uuid4().hex}{suffix}"
    try:
        with target.open("wb") as out:
            async for chunk in request.stream():
                await run_in_threadpool(out.write, chunk)
        if target.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="The upload was empty.")
        manifest = container.store.create(user.id, name.strip(), target, move=True)
    finally:
        target.unlink(missing_ok=True)  # no-op once moved
    return _summary(manifest)


@router.post("/{title_id}/process", status_code=202)
def process_title(
    title_id: str, body: ProcessRequest, container: ContainerDep, user: CurrentUser
) -> JobState:
    manifest = container.store.get(user.id, title_id)
    # Swearing is found from the words, not scanned, so only picture categories need a scanner.
    picture = set(body.filter_categories) & set(PICTURE_CATEGORIES)
    unsupported = picture - set(scannable_categories(container.settings))
    if unsupported:
        raise HTTPException(
            status_code=422,
            detail="This scanner can't check for "
            + " or ".join(sorted(c.value.replace("_", " ") for c in unsupported))
            + ".",
        )
    if body.dub_languages:
        available = dubbing_languages(container.providers)
        if not available:
            raise HTTPException(
                status_code=422, detail="Dubbing isn't set up on this computer yet."
            )
        unsupported_dubs = [lang for lang in body.dub_languages if lang not in available]
        if unsupported_dubs:
            names = " and ".join(language_name(lang) for lang in unsupported_dubs)
            raise HTTPException(status_code=422, detail=f"Dubbing can't speak {names}.")
    options = ProcessOptions(
        subtitle_languages=body.subtitle_languages,
        filter_categories=body.filter_categories,
        dub_languages=body.dub_languages,
        source_language=body.source_language,
    )
    return container.jobs.submit(manifest, options)


@router.get("/{title_id}/progress")
def progress(title_id: str, container: ContainerDep, user: CurrentUser) -> JobState:
    container.store.get(user.id, title_id)  # 404 for titles that aren't yours
    state = container.jobs.get(user.id, title_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Nothing is processing for this title.")
    return state
