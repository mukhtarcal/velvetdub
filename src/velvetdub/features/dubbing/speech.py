"""Speaks one line and fits it into the room it has."""

from pathlib import Path

from velvetdub.domain.dubbing import SynthesisRequest
from velvetdub.media.dialogue import wav_seconds
from velvetdub.media.tools import MediaTool
from velvetdub.providers.base import SpeechSynthesizer

MARGIN = 1.02  # ask for a hair faster than needed, since the pace is only approximate
STRETCH_FROM = 0.3  # seconds over, after speeding up, before the line is squeezed further
STRETCH_LIMIT = 1.2  # the most a finished line is squeezed (on top of any faster speaking)


class LineRecorder:
    """Records a line at the voice's natural pace; if it is too long for its room, asks for it
    faster (as far as the service allows); and as a last resort squeezes the recording a little.
    A line that still runs long is kept: the dub pushes the next line back, not cuts it."""

    def __init__(self, synthesizer: SpeechSynthesizer, media: MediaTool) -> None:
        self._synthesizer = synthesizer
        self._media = media

    def record(
        self, text: str, voice_id: str, language: str, slot: float, dest: Path
    ) -> tuple[float, float]:
        """Write the line to `dest` and return (speed used, seconds it lasts)."""
        request = SynthesisRequest(text=text, voice_id=voice_id, language=language)
        self._synthesizer.synthesize(request, dest)
        seconds = wav_seconds(dest)
        speed = 1.0
        if seconds > slot and self._synthesizer.max_speed > 1.0:
            speed = min(self._synthesizer.max_speed, seconds / slot * MARGIN)
            self._synthesizer.synthesize(request.model_copy(update={"speed": speed}), dest)
            seconds = wav_seconds(dest)
        if seconds > slot + STRETCH_FROM:
            factor = min(STRETCH_LIMIT, seconds / slot)
            squeezed = dest.with_name(f"{dest.stem}.squeezed.wav")
            self._media.change_tempo(dest, squeezed, factor)
            squeezed.replace(dest)
            speed *= factor
            seconds = wav_seconds(dest)
        return speed, seconds
