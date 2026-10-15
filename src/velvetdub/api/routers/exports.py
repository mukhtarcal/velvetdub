from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from velvetdub.api.deps import ContainerDep, CurrentUser
from velvetdub.services.exports import ExportState

router = APIRouter(prefix="/titles/{title_id}/export", tags=["export"])


@router.get("")
def export_state(title_id: str, container: ContainerDep, user: CurrentUser) -> ExportState:
    """How the cleaned copy is doing, and what it would be like with the cuts as they are now."""
    return container.exports.state(user.id, title_id)


@router.post("", status_code=202)
def start_export(title_id: str, container: ContainerDep, user: CurrentUser) -> ExportState:
    """Start making the cleaned copy from the cuts as they are now."""
    return container.exports.start(user.id, title_id)


@router.get("/file")
def export_file(title_id: str, container: ContainerDep, user: CurrentUser) -> FileResponse:
    found = container.exports.file(user.id, title_id)
    if found is None:
        raise HTTPException(status_code=409, detail="The cleaned copy isn't ready yet.")
    path, filename = found
    return FileResponse(path, media_type="video/mp4", filename=filename)
