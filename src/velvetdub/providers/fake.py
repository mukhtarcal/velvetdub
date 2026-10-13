"""Deterministic offline providers for tests and trying the pipeline without API keys.

Select with e.g. TRANSCRIPTION_PROVIDER=fake.
"""

import re
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel

from velvetdub.config.settings import Settings
from velvetdub.domain.frames import FrameJudgement, FrameQuestion
from velvetdub.domain.transcript import Segment, Transcript, Word
from velvetdub.providers.base import FrameJudge, TextGenerator, Transcriber, VideoAnalyzer
from velvetdub.providers.registry import (
    frame_judges,
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
    It relies on the prompt's 'Target language: xx' line and '[id] text' lines."""

    name = "fake"

    def generate[T: BaseModel](self, system: str, prompt: str, schema: type[T]) -> T:
        target = re.search(r"^Target language: (\S+)", prompt, re.MULTILINE)
        language = target.group(1) if target else "xx"
        lines = [
            {"id": found.group(1), "text": f"[{language}] {found.group(2)}"}
            for found in re.finditer(r"^\[(?!context\])([^\]]+)\] (.*)$", prompt, re.MULTILINE)
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
