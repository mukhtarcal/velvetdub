import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from velvetdub.api.deps import ContainerDep, CurrentUser
from velvetdub.services.subtitles import ScriptLine, SubtitleFormat

router = APIRouter(prefix="/titles/{title_id}", tags=["subtitles"])

_FILE = re.compile(r"^(?P<language>[A-Za-z0-9_-]{1,32})\.(?P<fmt>vtt|srt)$")


@router.get("/subtitles/{filename}")
def get_subtitles(
    title_id: str,
    filename: str,
    container: ContainerDep,
    user: CurrentUser,
    mask: bool = False,
    download: bool = False,
) -> PlainTextResponse:
    """Subtitles as VTT or SRT. With `mask`, words that are filtered are masked (*****)."""
    match = _FILE.match(filename)
    if match is None:
        raise HTTPException(status_code=404, detail="Subtitle file not found")
    fmt: SubtitleFormat = "srt" if match["fmt"] == "srt" else "vtt"
    body = container.subtitles.render(user.id, title_id, match["language"], mask=mask, fmt=fmt)
    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="{match["language"]}.{fmt}"'
    media = "text/vtt" if fmt == "vtt" else "application/x-subrip"
    return PlainTextResponse(body, media_type=f"{media}; charset=utf-8", headers=headers)


class ImportRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5_000_000)


@router.put("/subtitles/{language}/import")
def import_subtitles(
    title_id: str, language: str, body: ImportRequest, container: ContainerDep, user: CurrentUser
) -> dict[str, int]:
    """Replace a language's subtitles with the viewer's own SRT or VTT file."""
    return {"lines": container.subtitles.import_file(user.id, title_id, language, body.content)}


@router.get("/script/{language}")
def get_script(
    title_id: str, language: str, container: ContainerDep, user: CurrentUser
) -> list[ScriptLine]:
    return container.subtitles.script_lines(user.id, title_id, language)


class LineEdit(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.put("/script/{language}/{segment_id}", status_code=204)
def edit_line(
    title_id: str,
    language: str,
    segment_id: str,
    body: LineEdit,
    container: ContainerDep,
    user: CurrentUser,
) -> None:
    container.subtitles.edit_line(user.id, title_id, language, segment_id, body.text)
