"""Scans one clip of a film and returns filter events.

Two ways to do it, chosen by which provider `MODERATION_PROVIDER` names:

* `SceneScanner` hands the whole clip to a video model (Gemini) with the scene-filtering prompt.
* `FrameScanner` pulls a frame every second and has a frame judge (OpenAI Decisions) answer yes/no
  questions about each few-second window, then merges the flagged seconds into scenes.

The stage cuts the clips and saves each result; a scanner only says how it wants its clips cut
and what is in one.
"""

import tempfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from velvetdub.config.settings import Settings
from velvetdub.domain.filtering import FilterEvent
from velvetdub.domain.frames import FrameJudgement
from velvetdub.domain.usage import TokenUsage
from velvetdub.features.scene_filtering.detections import ClipResult, to_events
from velvetdub.features.scene_filtering.frame_prompt import intro_for, questions_for
from velvetdub.features.scene_filtering.frames import frame_events
from velvetdub.features.scene_filtering.prompt import PROMPT
from velvetdub.media.tools import MediaTool
from velvetdub.providers.base import FrameJudge, VideoAnalyzer

# Frames are sampled once per second, and each is judged together with its neighbours.
FRAME_FPS = 1.0
FRAME_HEIGHT = 720
FRAME_CRF = 20  # frames need a sharper picture than a video model does
WINDOW_RADIUS = 1  # a frame plus one either side: 3 frames
PARALLEL_REQUESTS = 8


class ClipScan(BaseModel):
    """One clip's finished result."""

    events: list[FilterEvent]
    usage: TokenUsage = TokenUsage()


class ClipSpec(BaseModel):
    """How the stage should cut the film for this scanner."""

    model_config = ConfigDict(frozen=True)

    seconds: int
    fps: float
    height: int
    crf: int = 30


class Scanner(Protocol):
    @property
    def identity(self) -> str: ...

    def clip_spec(self, settings: Settings) -> ClipSpec: ...

    def config_key(self, settings: Settings) -> str:
        """Everything about this scan that, if changed, means old results no longer apply."""
        ...

    def scan_clip(self, clip_path: Path, *, offset: float, media: MediaTool) -> ClipScan: ...


class SceneScanner:
    """Video-model scanner (Gemini)."""

    def __init__(self, analyzer: VideoAnalyzer) -> None:
        self._analyzer = analyzer

    @property
    def identity(self) -> str:
        return self._analyzer.identity

    def clip_spec(self, settings: Settings) -> ClipSpec:
        return ClipSpec(
            seconds=settings.scan_clip_seconds,
            fps=settings.visual_sample_fps,
            height=settings.scan_height,
        )

    def config_key(self, settings: Settings) -> str:
        return (
            f"{self.identity}|fps={settings.visual_sample_fps}"
            f"|clip={settings.scan_clip_seconds}|h={settings.scan_height}"
        )

    def scan_clip(self, clip_path: Path, *, offset: float, media: MediaTool) -> ClipScan:
        result = self._analyzer.analyze_clip(clip_path, PROMPT, ClipResult)
        events = to_events(result, offset=offset, source=self._analyzer.identity)
        return ClipScan(events=events, usage=self._analyzer.last_usage)


class FrameScanner:
    """Frame-by-frame scanner (OpenAI Decisions): nudity and sexual content only."""

    def __init__(self, judge: FrameJudge, threshold: float) -> None:
        self._judge = judge
        self._threshold = threshold

    @property
    def identity(self) -> str:
        return self._judge.identity

    def clip_spec(self, settings: Settings) -> ClipSpec:
        return ClipSpec(
            seconds=settings.scan_clip_seconds, fps=FRAME_FPS, height=FRAME_HEIGHT, crf=FRAME_CRF
        )

    def config_key(self, settings: Settings) -> str:
        return (
            f"{self.identity}|frames|window={2 * WINDOW_RADIUS + 1}|threshold={self._threshold}"
            f"|clip={settings.scan_clip_seconds}|h={FRAME_HEIGHT}"
        )

    def scan_clip(self, clip_path: Path, *, offset: float, media: MediaTool) -> ClipScan:
        with tempfile.TemporaryDirectory(prefix="vd-frames-") as scratch:
            frames = media.extract_frames(clip_path, Path(scratch))
            judgements = self._judge_all(frames)
        events = frame_events(
            [j.probabilities for j in judgements],
            offset=offset,
            source=self.identity,
            threshold=self._threshold,
        )
        usage = sum((j.usage for j in judgements), TokenUsage())
        return ClipScan(events=events, usage=usage)

    def _judge_all(self, frames: Sequence[Path]) -> list[FrameJudgement]:
        def window(second: int) -> list[Path]:
            return list(
                frames[
                    max(0, second - WINDOW_RADIUS) : min(len(frames), second + WINDOW_RADIUS + 1)
                ]
            )

        def judge(second: int) -> FrameJudgement:
            shown = window(second)
            return self._judge.judge(shown, intro_for(len(shown)), questions_for(len(shown)))

        pool = ThreadPoolExecutor(max_workers=PARALLEL_REQUESTS)
        try:
            return list(pool.map(judge, range(len(frames))))
        finally:
            pool.shutdown(wait=True, cancel_futures=True)  # stop queued requests after a failure
