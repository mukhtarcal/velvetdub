"""Scene filtering feature with a stand-in video model: checks how answers become events."""

from pathlib import Path

import pytest
from pydantic import BaseModel

from tests.conftest import FakeMediaTool
from velvetdub.config.settings import Settings
from velvetdub.domain.filtering import FilterCategory, Severity
from velvetdub.errors import ProviderError
from velvetdub.features.scene_filtering.categories import PICTURE_CATEGORIES
from velvetdub.features.scene_filtering.detections import (
    ClipResult,
    Detection,
    VisualCategory,
    parse_clock,
)
from velvetdub.features.scene_filtering.prompt import build_prompt
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
    scanner = SceneScanner(StubAnalyzer(result), PICTURE_CATEGORIES)
    return scanner.scan_clip(Path("c.mp4"), offset=offset, media=FakeMediaTool()).events


def test_the_scan_asks_with_instructions_built_from_the_chosen_categories(tmp_path: Path) -> None:
    analyzer = StubAnalyzer(ClipResult(detections=[]))
    chosen = [FilterCategory.VIOLENCE, FilterCategory.NUDITY]
    SceneScanner(analyzer, chosen).scan_clip(tmp_path / "c.mp4", offset=0, media=FakeMediaTool())
    assert analyzer.instructions == [build_prompt(chosen)]


def test_the_prompt_mentions_only_the_chosen_categories_in_a_fixed_order() -> None:
    prompt = build_prompt([FilterCategory.VIOLENCE, FilterCategory.NUDITY])
    assert "- nudity: partial or full nudity" in prompt
    assert "- violence: fights, weapons" in prompt
    assert prompt.index("- nudity:") < prompt.index("- violence:")  # not the order ticked
    for left_out in ("sexual_content", "scary_scenes", "drugs_and_drinking"):
        assert left_out not in prompt
    assert build_prompt([FilterCategory.VIOLENCE, FilterCategory.NUDITY]) == build_prompt(
        [FilterCategory.NUDITY, FilterCategory.VIOLENCE, FilterCategory.NUDITY]
    )


def test_the_prompt_ignores_categories_the_picture_scan_does_not_cover() -> None:
    assert "- swearing:" not in build_prompt([FilterCategory.SWEARING, FilterCategory.NUDITY])


def test_every_offered_category_has_its_own_line() -> None:
    for category in PICTURE_CATEGORIES:
        assert f"- {category.value}:" in build_prompt([category])


def test_the_scan_key_changes_with_the_chosen_categories(settings: Settings) -> None:
    analyzer = StubAnalyzer(ClipResult(detections=[]))
    nudity = SceneScanner(analyzer, [FilterCategory.NUDITY]).config_key(settings)
    both = SceneScanner(analyzer, [FilterCategory.NUDITY, FilterCategory.VIOLENCE])
    assert nudity != both.config_key(settings)
    swapped = SceneScanner(analyzer, [FilterCategory.VIOLENCE, FilterCategory.NUDITY])
    assert both.config_key(settings) == swapped.config_key(settings)


def test_a_stray_answer_outside_the_chosen_categories_is_dropped(tmp_path: Path) -> None:
    result = ClipResult(
        detections=[
            detection("00:01", "00:02", VisualCategory.VIOLENCE),
            detection("00:05", "00:06", VisualCategory.NUDITY),
        ]
    )
    scanner = SceneScanner(StubAnalyzer(result), [FilterCategory.NUDITY])
    events = scanner.scan_clip(tmp_path / "c.mp4", offset=0, media=FakeMediaTool()).events
    assert [e.category for e in events] == [FilterCategory.NUDITY]


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
