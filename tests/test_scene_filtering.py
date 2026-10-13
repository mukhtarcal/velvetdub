"""Scene filtering feature with a stand-in video model: checks how answers become events."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from velvetdub.domain.filtering import FilterCategory, Severity
from velvetdub.errors import ProviderError
from velvetdub.features.scene_filtering.detections import (
    ClipResult,
    Detection,
    VisualCategory,
    parse_clock,
)
from velvetdub.features.scene_filtering.prompt import PROMPT
from velvetdub.features.scene_filtering.scanner import SceneScanner
from velvetdub.providers.base import VideoAnalyzer


class StubAnalyzer(VideoAnalyzer):
    name = "stub"

    def __init__(self, result: ClipResult) -> None:
        super().__init__("m")
        self._result = result
        self.instructions: list[str] = []

    def analyze_clip[T: BaseModel](self, clip_path: Path, instructions: str, schema: type[T]) -> T:
        self.instructions.append(instructions)
        return schema.model_validate(self._result.model_dump())


def detection(
    start: str, end: str, category: VisualCategory = VisualCategory.VIOLENCE
) -> Detection:
    return Detection(
        start=start, end=end, category=category, severity="strong", confidence=0.9, description="d"
    )


def scan(result: ClipResult, offset: float = 0) -> list:  # type: ignore[type-arg]
    return SceneScanner(StubAnalyzer(result)).scan_clip(Path("c.mp4"), offset=offset).events


def test_the_scan_asks_with_the_scene_filtering_instructions(tmp_path: Path) -> None:
    analyzer = StubAnalyzer(ClipResult(detections=[]))
    SceneScanner(analyzer).scan_clip(tmp_path / "c.mp4", offset=0)
    assert analyzer.instructions == [PROMPT]


def test_detections_are_shifted_onto_the_film_timeline() -> None:
    (event,) = scan(ClipResult(detections=[detection("01:05", "01:20")]), offset=600)
    assert (event.start, event.end) == (665.0, 680.0)
    assert event.category is FilterCategory.VIOLENCE
    assert event.severity is Severity.STRONG
    assert event.source == "stub:m"


def test_backwards_range_is_repaired_not_dropped() -> None:
    (event,) = scan(ClipResult(detections=[detection("00:30", "00:10")]))
    assert event.start == event.end == 30.0


def test_confidence_is_clamped() -> None:
    found = detection("00:01", "00:02")
    found.confidence = 7
    (event,) = scan(ClipResult(detections=[found]))
    assert event.confidence == 1.0


@pytest.mark.parametrize(
    ("text", "seconds"), [("00:07", 7), ("1:02:03", 3723), ("90", 90), (" 02:30 ", 150)]
)
def test_parse_clock(text: str, seconds: float) -> None:
    assert parse_clock(text) == seconds


def test_parse_clock_rejects_garbage() -> None:
    with pytest.raises(ProviderError):
        parse_clock("soon")
