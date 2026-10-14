import mimetypes

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from velvetdub.api.deps import ContainerDep, CurrentUser

router = APIRouter(prefix="/titles/{title_id}/media", tags=["media"])


@router.get("/source")
def source_video(title_id: str, container: ContainerDep, user: CurrentUser) -> FileResponse:
    """The original film. Supports Range requests, so the player can seek."""
    manifest = container.store.get(user.id, title_id)
    path = container.store.paths(manifest).source
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Video file is missing")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type)


POSTER_CACHE = {"Cache-Control": "private, max-age=3600"}


@router.get("/poster")
def poster(title_id: str, container: ContainerDep, user: CurrentUser) -> FileResponse:
    """A picture from the film for the library (see `services/posters.py`). It is a 404 until
    the film has been scanned, and the page shows the harbor scene instead."""
    path = container.posters.get(user.id, title_id)
    if path is None:
        raise HTTPException(status_code=404, detail="No picture for this title yet.")
    return FileResponse(path, media_type="image/jpeg", headers=POSTER_CACHE)


@router.get("/audio/{track_id}")
def audio_track(
    title_id: str, track_id: str, container: ContainerDep, user: CurrentUser
) -> FileResponse:
    manifest = container.store.get(user.id, title_id)
    # Look the track up in the manifest rather than building a path from the URL
    track = next((t for t in manifest.audio_tracks if t.id == track_id), None)
    if track is None:
        raise HTTPException(status_code=404, detail="Audio track not found")
    path = container.store.paths(manifest).root / track.path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Audio file is missing")
    return FileResponse(path, media_type="audio/mp4")
