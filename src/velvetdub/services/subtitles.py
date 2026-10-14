"""Subtitle rendering (with filtered words masked), export, line editing and import."""

from typing import Literal

from pydantic import BaseModel

from velvetdub.domain.manifest import SubtitleTrack
from velvetdub.domain.transcript import Transcript
from velvetdub.domain.translation import TranslatedSegment, Translation
from velvetdub.errors import VelvetDubError
from velvetdub.services.playback import PlaybackService
from velvetdub.storage.artifacts import read_model, write_model
from velvetdub.storage.title_store import TitleStore
from velvetdub.subtitles.formats import Cue, format_srt, format_webvtt, parse_cues
from velvetdub.subtitles.masking import mask_cues

SubtitleFormat = Literal["vtt", "srt"]


class ScriptLine(BaseModel):
    segment_id: str
    start: float
    end: float
    speaker: str | None
    original: str
    text: str


class SubtitleNotFoundError(VelvetDubError):
    """The title has no subtitles in that language."""


class SubtitleService:
    def __init__(self, store: TitleStore, playback: PlaybackService) -> None:
        self._store = store
        self._playback = playback

    def render(
        self,
        owner_id: str,
        title_id: str,
        language: str,
        *,
        mask: bool,
        fmt: SubtitleFormat = "vtt",
    ) -> str:
        manifest = self._store.get(owner_id, title_id)
        if language not in {t.language for t in manifest.subtitle_tracks}:
            raise SubtitleNotFoundError(language)
        cues = parse_cues(self._store.paths(manifest).subtitles(language).read_text("utf-8"))
        if mask:
            filters = self._playback.resolved_filters(owner_id, title_id)
            cues = mask_cues(cues, filters)
        return format_srt(cues) if fmt == "srt" else format_webvtt(cues)

    def import_file(self, owner_id: str, title_id: str, language: str, content: str) -> int:
        """Replace a language's subtitles with the viewer's own SRT/VTT. Returns the line count."""
        cues = parse_cues(content)  # validate before touching anything
        manifest = self._store.get(owner_id, title_id)
        paths = self._store.paths(manifest)
        target = paths.subtitles(language)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(format_webvtt(cues), encoding="utf-8")
        manifest.upsert_subtitle_track(
            SubtitleTrack(language=language, path=paths.relative(target))
        )
        self._store.save(manifest)
        return len(cues)

    # --- script editor ---------------------------------------------------------------

    def script_lines(self, owner_id: str, title_id: str, language: str) -> list["ScriptLine"]:
        manifest = self._store.get(owner_id, title_id)
        source = {
            s.id: s for s in read_model(self._store.paths(manifest).transcript, Transcript).segments
        }
        return [
            ScriptLine(
                segment_id=t.segment_id,
                start=source[t.segment_id].start,
                end=source[t.segment_id].end,
                speaker=source[t.segment_id].speaker,
                original=source[t.segment_id].text,
                text=t.text,
            )
            for t in self.get_script(owner_id, title_id, language).segments
        ]

    def get_script(self, owner_id: str, title_id: str, language: str) -> Translation:
        manifest = self._store.get(owner_id, title_id)
        path = self._store.paths(manifest).translation(language)
        if not path.exists():
            raise SubtitleNotFoundError(language)
        return read_model(path, Translation)

    def edit_line(
        self, owner_id: str, title_id: str, language: str, segment_id: str, text: str
    ) -> None:
        """Change one line's text and rewrite that language's subtitle file."""
        manifest = self._store.get(owner_id, title_id)
        paths = self._store.paths(manifest)
        translation = self.get_script(owner_id, title_id, language)
        if segment_id not in {s.segment_id for s in translation.segments}:
            raise SubtitleNotFoundError(segment_id)
        updated = translation.model_copy(
            update={
                "segments": [
                    TranslatedSegment(
                        segment_id=s.segment_id, text=text, target_duration=s.target_duration
                    )
                    if s.segment_id == segment_id
                    else s
                    for s in translation.segments
                ]
            }
        )
        write_model(paths.translation(language), updated)

        timing = {s.id: s for s in read_model(paths.transcript, Transcript).segments}
        cues = [
            Cue(
                start=timing[t.segment_id].start,
                end=timing[t.segment_id].end,
                text=t.text,
            )
            for t in updated.segments
        ]
        paths.subtitles(language).write_text(format_webvtt(cues), encoding="utf-8")
