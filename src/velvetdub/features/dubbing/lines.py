"""Records every line of a dub, paying only for lines that are new or changed."""

import hashlib
from collections.abc import Callable, Collection
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from velvetdub.domain.dubbing import DubLine, DubLines, DubVoices
from velvetdub.domain.transcript import Segment, Transcript
from velvetdub.domain.translation import Translation
from velvetdub.features.dubbing.samples import speaker_key
from velvetdub.features.dubbing.speech import (
    FIT_SLACK,
    RUNAWAY_FROM,
    RUNAWAY_SHARE,
    LineRecorder,
)
from velvetdub.features.dubbing.timing import slots
from velvetdub.media.dialogue import trim_silence


@dataclass
class _Done:
    segment: Segment
    line: DubLine | None  # None: left as the film has it


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
    skip: Collection[str] = (),
    previous: DubLines | None = None,
) -> DubLines:
    """One recording per line of the translation, in the speaker's copied voice.

    A recording is named after what made it (text, voice, room, service), so one that is already
    on disk is reused. That is what makes a stopped run resume, and an edit re-record one line.
    Lines in `skip` (crowd chants) are not recorded: the film's own sound is kept there. Every
    recording has the silence trimmed off its ends. A recording made before takes were counted
    that clearly does not fit its room is asked for again, once."""
    texts = {t.segment_id: t.text.strip() for t in translation.segments}
    room = slots(transcript.segments, film_seconds)
    fallback = next(iter(voices.voices.values()))
    language = translation.language
    earlier = {line.key: line for line in previous.lines} if previous else {}

    def work(item: tuple[Segment, float]) -> _Done:
        segment, slot = item
        text = texts.get(segment.id, "")
        if not text or segment.id in skip:
            return _Done(segment, None)
        voice = voices.voices.get(speaker_key(segment.speaker), fallback)
        seed = f"{identity}|{language}|{voice}|{slot:.2f}|{text}"
        key = hashlib.sha256(seed.encode()).hexdigest()[:12]
        # Named by what it is, not by its place in the film: numbering shifts when a line is
        # split in two, and every later line must still be found.
        path = line_path(key)
        older = line_path(f"{segment.id}-{key}")  # how earlier versions named it
        if not path.exists() and older.exists():
            older.replace(path)
        takes = earlier[key].takes if key in earlier else 0
        if path.exists():
            seconds, _ = trim_silence(path)
            if takes == 0 and _does_not_fit(seconds, slot):
                path.unlink()  # recorded before takes were tried: ask again, once
        if not path.exists():
            partial = path.with_name(f"{path.stem}.part.wav")
            recorded = recorder.record(text, voice, language, slot, partial)
            if recorded is None:
                return _Done(segment, None)  # the voice made no sound: keep the film's own
            partial.replace(path)
            takes = recorded.takes
        return _Done(
            segment,
            DubLine(
                segment_id=segment.id,
                start=segment.start,
                slot=slot,
                text=text,
                voice_id=voice,
                key=key,
                duration=trim_silence(path)[0],
                path=relative(path),
                takes=takes,
            ),
        )

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        done = list(pool.map(work, zip(transcript.segments, room, strict=True)))
    lines = [d.line for d in done if d.line is not None]
    kept = [d.segment.id for d in done if d.line is None and texts.get(d.segment.id)]
    _discard_unused(lines, line_path, relative)
    return DubLines(language=language, lines=lines, kept_original=kept)


def _does_not_fit(seconds: float, slot: float) -> bool:
    """Far too long for its room, not merely a little over (which squeezing handles)."""
    over = seconds - slot
    return over > FIT_SLACK and over > max(RUNAWAY_FROM, RUNAWAY_SHARE * slot)


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
