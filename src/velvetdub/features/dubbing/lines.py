"""Records every line of a dub, paying only for lines that are new or changed."""

import hashlib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from velvetdub.domain.dubbing import DubLine, DubLines, DubVoices
from velvetdub.domain.transcript import Segment, Transcript
from velvetdub.domain.translation import Translation
from velvetdub.features.dubbing.samples import speaker_key
from velvetdub.features.dubbing.speech import LineRecorder
from velvetdub.features.dubbing.timing import slots
from velvetdub.media.dialogue import wav_seconds


def record_lines(
    *,
    transcript: Transcript,
    translation: Translation,
    voices: DubVoices,
    film_seconds: float,
    recorder: LineRecorder,
    identity: str,
    line_path: Callable[[str], Path],
    relative: Callable[[Path], str],
    concurrency: int,
) -> DubLines:
    """One recording per line of the translation, in the speaker's copied voice.

    A recording is named after what made it (text, voice, room, service), so one that is already
    on disk is reused. That is what makes a stopped run resume, and an edit re-record one line."""
    texts = {t.segment_id: t.text.strip() for t in translation.segments}
    room = slots(transcript.segments, film_seconds)
    fallback = next(iter(voices.voices.values()))
    language = translation.language

    def work(item: tuple[Segment, float]) -> DubLine | None:
        segment, slot = item
        text = texts.get(segment.id, "")
        if not text:
            return None
        voice = voices.voices.get(speaker_key(segment.speaker), fallback)
        seed = f"{identity}|{language}|{voice}|{slot:.2f}|{text}"
        key = hashlib.sha256(seed.encode()).hexdigest()[:12]
        path = line_path(f"{segment.id}-{key}")
        if not path.exists():
            partial = path.with_name(f"{path.stem}.part.wav")
            recorder.record(text, voice, language, slot, partial)
            partial.replace(path)
        return DubLine(
            segment_id=segment.id,
            start=segment.start,
            slot=slot,
            text=text,
            voice_id=voice,
            key=key,
            duration=wav_seconds(path),
            path=relative(path),
        )

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        recorded = list(pool.map(work, zip(transcript.segments, room, strict=True)))
    lines = [line for line in recorded if line is not None]
    _discard_unused(lines, line_path, relative)
    return DubLines(language=language, lines=lines)


def _discard_unused(
    lines: list[DubLine], line_path: Callable[[str], Path], relative: Callable[[Path], str]
) -> None:
    """Remove recordings of lines that have since changed, and any half-written ones."""
    if not lines:
        return
    folder = line_path("x").parent
    keep = {line.path for line in lines}
    for path in folder.glob("*.wav"):
        if relative(path) not in keep:
            path.unlink(missing_ok=True)
