"""Deterministic offline providers for tests and trying the pipeline without API keys.

Select with e.g. TRANSCRIPTION_PROVIDER=fake.
"""

import re
import wave
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from velvetdub.config.settings import Settings
from velvetdub.domain.dubbing import LINE_SAMPLE_RATE, SeparatedStems, SynthesisRequest, Voice
from velvetdub.domain.frames import FrameJudgement, FrameQuestion
from velvetdub.domain.transcript import Segment, Transcript, Word
from velvetdub.providers.base import (
    FrameJudge,
    SourceSeparator,
    SpeechSynthesizer,
    TextGenerator,
    Transcriber,
    VideoAnalyzer,
)
from velvetdub.providers.registry import (
    frame_judges,
    separators,
    synthesizers,
    text_generators,
    transcribers,
    video_analyzers,
)


class FakeTranscriber(Transcriber):
    name = "fake"

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        lines = [
            ("Hello there, friend.", 1.0, 3.0),
            ("What the hell is that?", 4.0, 6.0),
        ]
        segments = []
        for i, (text, start, end) in enumerate(lines):
            tokens = text.split()
            step = (end - start) / len(tokens)
            words = tuple(
                Word(text=t, start=start + n * step, end=start + (n + 1) * step)
                for n, t in enumerate(tokens)
            )
            segments.append(
                Segment(id=f"s{i}", start=start, end=end, text=text, speaker="A", words=words)
            )
        return Transcript(language=language or "en", segments=segments)


class FakeTextGenerator(TextGenerator):
    """Answers the translation prompt offline: every numbered line comes back as '[lang] text'.
    It relies on the prompt's 'Target language: xx' line and '[id] text' lines (a leading
    '(2.3s)' timing hint is dropped)."""

    name = "fake"

    def generate[T: BaseModel](self, system: str, prompt: str, schema: type[T]) -> T:
        target = re.search(r"^Target language: (\S+)", prompt, re.MULTILINE)
        language = target.group(1) if target else "xx"
        lines = [
            {"id": found.group(1), "text": f"[{language}] {found.group(2)}"}
            for found in re.finditer(
                r"^\[(?!context\])([^\]]+)\] (?:\(\d+(?:\.\d+)?s\) )?(.*)$", prompt, re.MULTILINE
            )
        ]
        return schema.model_validate({"lines": lines})


class FakeVideoAnalyzer(VideoAnalyzer):
    """Answers the scene scan offline: one violent moment, 10 to 20 seconds into every clip."""

    name = "fake"

    def analyze_clip[T: BaseModel](self, clip_path: Path, instructions: str, schema: type[T]) -> T:
        return schema.model_validate(
            {
                "detections": [
                    {
                        "start": "00:10",
                        "end": "00:20",
                        "category": "violence",
                        "severity": "strong",
                        "confidence": 0.9,
                        "description": "fake detection",
                    }
                ]
            }
        )


class FakeFrameJudge(FrameJudge):
    """Offline frame judge: flags the window centred on the 11th frame, and nothing else."""

    name = "fake-frames"

    def judge(
        self, frames: Sequence[Path], intro: str, questions: Sequence[FrameQuestion]
    ) -> FrameJudgement:
        flagged = frames[len(frames) // 2].name == "f_00011.jpg" if frames else False
        return FrameJudgement(probabilities={q.name: 0.9 if flagged else 0.0 for q in questions})


def write_silence(
    dest: Path, seconds: float, *, channels: int = 1, rate: int = LINE_SAMPLE_RATE
) -> None:
    """A WAV of silence, for fakes and tests."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(b"\x00\x00" * channels * int(seconds * rate))


class FakeSeparator(SourceSeparator):
    """Writes two short silent stems, as the real one would for a film."""

    name = "fake"

    def separate(self, audio_path: Path, out_dir: Path) -> SeparatedStems:
        dialogue, background = out_dir / "dialogue.wav", out_dir / "background.wav"
        write_silence(dialogue, 1.0, channels=2, rate=44100)
        write_silence(background, 1.0, channels=2, rate=44100)
        return SeparatedStems(dialogue=dialogue, background=background)


class FakeSynthesizer(SpeechSynthesizer):
    """Speaks every line as silence of a length that follows its text: 0.05 s a character, divided
    by the speed. Records what it was asked, so tests can count calls."""

    name = "fake"
    supports_cloning = True
    max_speed = 1.5

    def __init__(self, model: str | None = None) -> None:
        super().__init__(model)
        self.spoken: list[SynthesisRequest] = []
        self.cloned: list[str] = []

    def languages(self) -> frozenset[str]:
        return frozenset({"en", "es", "ar"})

    def list_voices(self, language: str | None = None) -> list[Voice]:
        return [Voice(id="stock", name="Stock")]

    def synthesize(self, request: SynthesisRequest, dest: Path) -> Path:
        self.spoken.append(request)
        write_silence(dest, max(0.2, 0.05 * len(request.text)) / request.speed)
        return dest

    def clone_voice(self, sample: Path, name: str, language: str) -> Voice:
        self.cloned.append(name)
        return Voice(id=f"clone-{name}", name=name, language=language)

    def delete_voice(self, voice_id: str) -> None:
        self.cloned = [n for n in self.cloned if f"clone-{n}" != voice_id]


@separators.register("fake")
def _separator(settings: Settings) -> SourceSeparator:
    return FakeSeparator()


@synthesizers.register("fake")
def _synthesizer(settings: Settings) -> SpeechSynthesizer:
    return FakeSynthesizer()


@transcribers.register("fake")
def _transcriber(settings: Settings) -> Transcriber:
    return FakeTranscriber()


@text_generators.register("fake")
def _text_generator(settings: Settings) -> TextGenerator:
    return FakeTextGenerator()


@frame_judges.register("fake-frames")
def _frame_judge(settings: Settings) -> FrameJudge:
    return FakeFrameJudge(settings.moderation_model)


@video_analyzers.register("fake")
def _video_analyzer(settings: Settings) -> VideoAnalyzer:
    return FakeVideoAnalyzer(settings.moderation_model)
