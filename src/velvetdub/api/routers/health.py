from fastapi import APIRouter
from pydantic import BaseModel

from velvetdub import __version__
from velvetdub.api.deps import ContainerDep
from velvetdub.domain.filtering import FilterCategory
from velvetdub.features.scene_filtering.factory import scannable_categories

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


class Capabilities(BaseModel):
    scan_categories: list[FilterCategory]


@router.get("/capabilities")
def capabilities(container: ContainerDep) -> Capabilities:
    """What this install can do, so the UI can grey out choices the chosen scanner can't check."""
    return Capabilities(scan_categories=list(scannable_categories(container.settings)))
