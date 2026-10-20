"""Where a title's files live. The only place that knows the folder layout."""

import re
from pathlib import Path

from velvetdub.errors import InvalidNameError

_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")


def safe_name(value: str) -> str:
    """Language codes and track ids end up in file names, so only plain names are allowed."""
    if not _SAFE_NAME.fullmatch(value):
        raise InvalidNameError(f"Not a valid name: {value!r}")
    return value


class TitlePaths:
    def __init__(self, root: Path, source_filename: str) -> None:
        self.root = root
        self._source_filename = source_filename

    @property
    def manifest(self) -> Path:
        return self.root / "manifest.json"

    @property
    def source(self) -> Path:
        return self.root / self._source_filename

    @property
    def original_audio(self) -> Path:
        return self.root / "audio" / "original.m4a"

    def audio_track(self, track_id: str) -> Path:
        """Dubs: audio/<track_id>.m4a"""
        return self.root / "audio" / f"{safe_name(track_id)}.m4a"

    # --- Dubbing: everything under dubbing/ can be thrown away and made again ---

    @property
    def dub_mix(self) -> Path:
        """The film's whole sound, only while the voices are being separated."""
        return self.root / "dubbing" / "mix.wav"

    @property
    def dub_stems(self) -> Path:
        return self.root / "dubbing" / "stems"

    @property
    def dub_dialogue(self) -> Path:
        return self.dub_stems / "dialogue.wav"

    @property
    def dub_background(self) -> Path:
        return self.dub_stems / "background.wav"

    @property
    def dub_speech(self) -> Path:
        """The dialogue stem, small enough to send to the transcription service."""
        return self.root / "dubbing" / "dialogue.m4a"

    @property
    def dub_heard(self) -> Path:
        """The transcription as the service returned it, before it is shaped into sentences."""
        return self.root / "dubbing" / "heard.json"

    @property
    def dub_transcript(self) -> Path:
        """What was said, in whole sentences, heard from the dialogue stem alone."""
        return self.root / "dubbing" / "transcript.json"

    def dub_translation(self, language: str) -> Path:
        return self.root / "dubbing" / "translations" / f"{safe_name(language)}.json"

    def dub_sample(self, speaker: str) -> Path:
        """A stretch of one speaker's voice, sent to be copied."""
        return self.root / "dubbing" / "samples" / f"{safe_name(speaker)}.wav"

    @property
    def dub_voices(self) -> Path:
        return self.root / "dubbing" / "voices.json"

    def dub_lines(self, language: str) -> Path:
        """The index of recorded lines for one language."""
        return self.root / "dubbing" / safe_name(language) / "lines.json"

    def dub_line(self, language: str, name: str) -> Path:
        """One recorded line. `name` carries the line's id and a key for what was recorded, so a
        changed line gets a new file and an unchanged one is found again."""
        return self.root / "dubbing" / safe_name(language) / "lines" / f"{safe_name(name)}.wav"

    @property
    def poster(self) -> Path:
        """The picture shown for the title in the library, taken from the film itself."""
        return self.root / "poster.jpg"

    @property
    def export_video(self) -> Path:
        """The cleaned copy of the film, made on request (the source is never changed)."""
        return self.root / "exports" / "cleaned.mp4"

    @property
    def export_record(self) -> Path:
        """Which cuts `export_video` was made from, so an unchanged export is not made again."""
        return self.root / "exports" / "cleaned.json"

    @property
    def transcript(self) -> Path:
        return self.root / "transcript.json"

    def translation(self, language: str) -> Path:
        return self.root / "translations" / f"{safe_name(language)}.json"

    @property
    def visual_events(self) -> Path:
        return self.root / "scan" / "visual.json"

    def visual_part(self, key: str, index: int) -> Path:
        """Saved result of one scanned clip, so a stopped scan resumes instead of restarting.
        `key` ties it to the scan settings that produced it."""
        return self.root / "scan" / "parts" / safe_name(key) / f"clip_{index:04d}.json"

    @property
    def visual_usage(self) -> Path:
        return self.root / "scan" / "visual_usage.json"

    @property
    def filters(self) -> Path:
        return self.root / "filters.json"

    @property
    def overrides(self) -> Path:
        return self.root / "overrides.json"

    def subtitles(self, language: str) -> Path:
        return self.root / "subtitles" / f"{safe_name(language)}.vtt"

    def relative(self, path: Path) -> str:
        """Path as stored in the manifest (relative to the title folder)."""
        return path.relative_to(self.root).as_posix()
