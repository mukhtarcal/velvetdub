"""Scans one clip of a film: asks the video model what is in it and returns filter events."""

from pathlib import Path

from pydantic import BaseModel

from velvetdub.domain.filtering import FilterEvent
from velvetdub.domain.usage import TokenUsage
from velvetdub.features.scene_filtering.detections import ClipResult, to_events
from velvetdub.features.scene_filtering.prompt import PROMPT
from velvetdub.providers.base import VideoAnalyzer


class ClipScan(BaseModel):
    """One clip's finished result."""

    events: list[FilterEvent]
    usage: TokenUsage = TokenUsage()


class SceneScanner:
    def __init__(self, analyzer: VideoAnalyzer) -> None:
        self._analyzer = analyzer

    @property
    def identity(self) -> str:
        return self._analyzer.identity

    def scan_clip(self, clip_path: Path, *, offset: float) -> ClipScan:
        result = self._analyzer.analyze_clip(clip_path, PROMPT, ClipResult)
        events = to_events(result, offset=offset, source=self._analyzer.identity)
        return ClipScan(events=events, usage=self._analyzer.last_usage)
