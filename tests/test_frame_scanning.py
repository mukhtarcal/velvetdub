"""Frame-by-frame scene scanning (OpenAI Decisions path), with the network call replaced."""

from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import httpx2
import openai
import pytest

from tests.conftest import FakeMediaTool
from velvetdub.config.settings import Settings
from velvetdub.container import build_container
from velvetdub.domain.filtering import FilterCategory, FilterTimeline, Severity
from velvetdub.domain.frames import FrameJudgement, FrameQuestion
from velvetdub.domain.usage import TokenUsage
from velvetdub.errors import ProviderError, QuotaExceededError, UnknownProviderError
from velvetdub.features.scene_filtering.categories import PICTURE_CATEGORIES
from velvetdub.features.scene_filtering.factory import build_scene_scanner, scannable_categories
from velvetdub.features.scene_filtering.frame_prompt import NUDITY, SEXUAL, questions_for
from velvetdub.features.scene_filtering.frames import frame_events
from velvetdub.features.scene_filtering.scanner import FrameScanner, SceneScanner
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.providers.base import FrameJudge
from velvetdub.providers.openai_decisions import OpenAIFrameJudge
from velvetdub.providers.provider_set import ProviderSet
from velvetdub.storage.artifacts import read_model

# --- turning per-second answers into scenes ------------------------------------------------


def seconds(count: int, **flagged: dict[int, float]) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = [{NUDITY: 0.0, SEXUAL: 0.0} for _ in range(count)]
    for question, by_second in flagged.items():
        for second, value in by_second.items():
            rows[second][question] = value
    return rows


def test_flagged_seconds_close_together_become_one_scene_on_the_film_timeline() -> None:
    rows = seconds(30, nudity={10: 0.95, 12: 0.97, 15: 0.9})  # gaps of 2 and 3 seconds
    (event,) = frame_events(rows, offset=600, source="s", threshold=0.5)
    assert (event.start, event.end) == (610.0, 616.0)  # the last flagged second covers 15-16
    assert event.category is FilterCategory.NUDITY
    assert event.severity is Severity.STRONG
    assert event.confidence == 0.97
    assert event.id == "vis-600-0"


def test_a_long_gap_starts_a_new_scene() -> None:
    rows = seconds(30, nudity={5: 0.9, 20: 0.9})
    assert [(e.start, e.end) for e in frame_events(rows, offset=0, source="s", threshold=0.5)] == [
        (5.0, 6.0),
        (20.0, 21.0),
    ]


def test_scores_below_the_threshold_are_ignored_and_a_lower_threshold_catches_more() -> None:
    rows = seconds(10, sexual={4: 0.1})
    assert frame_events(rows, offset=0, source="s", threshold=0.5) == []
    (event,) = frame_events(rows, offset=0, source="s", threshold=0.05)
    assert event.category is FilterCategory.SEXUAL_CONTENT
    assert event.severity is Severity.MILD


def test_nudity_and_sexual_content_are_separate_events_in_time_order() -> None:
    rows = seconds(30, nudity={20: 0.95}, sexual={3: 0.7})
    events = frame_events(rows, offset=0, source="s", threshold=0.5)
    assert [(e.category.value, e.start) for e in events] == [
        ("sexual_content", 3.0),
        ("nudity", 20.0),
    ]
    assert events[0].severity is Severity.MODERATE


# --- the scanner ---------------------------------------------------------------------------


class StubJudge(FrameJudge):
    name = "stub"

    def __init__(self, flag_frame: str | None = None, fail_on_call: int | None = None) -> None:
        super().__init__("m")
        self.windows: list[list[str]] = []
        self.intros: list[str] = []
        self._flag_frame = flag_frame
        self._fail_on_call = fail_on_call

    def judge(
        self, frames: Sequence[Path], intro: str, questions: Sequence[FrameQuestion]
    ) -> FrameJudgement:
        self.windows.append([f.name for f in frames])
        self.intros.append(intro)
        if self._fail_on_call is not None and len(self.windows) == self._fail_on_call:
            raise QuotaExceededError("used up")
        hit = self._flag_frame is not None and frames[len(frames) // 2].name == self._flag_frame
        return FrameJudgement(
            probabilities={q.name: 0.95 if hit else 0.0 for q in questions},
            usage=TokenUsage(input_tokens=100, output_tokens=0),
        )


FRAME_CHOICES = [FilterCategory.NUDITY, FilterCategory.SEXUAL_CONTENT]


def scan(judge: FrameJudge, threshold: float = 0.5, offset: float = 600):  # type: ignore[no-untyped-def]
    return FrameScanner(judge, threshold, FRAME_CHOICES).scan_clip(
        Path("clip.mp4"), offset=offset, media=FakeMediaTool()
    )


def test_each_second_is_judged_with_its_neighbours() -> None:
    judge = StubJudge()
    scan(judge)
    windows = sorted(judge.windows)
    assert len(windows) == 30  # the fake clip has 30 frames
    assert ["f_00001.jpg", "f_00002.jpg"] in windows  # the first second has no earlier neighbour
    assert ["f_00009.jpg", "f_00010.jpg", "f_00011.jpg"] in windows
    assert ["f_00029.jpg", "f_00030.jpg"] in windows
    assert any("3 consecutive frames" in intro for intro in judge.intros)


def test_flagged_windows_become_events_and_token_usage_is_summed() -> None:
    result = scan(StubJudge(flag_frame="f_00011.jpg"))  # the 10th second of the clip
    assert {e.category.value for e in result.events} == {"nudity", "sexual_content"}
    assert all((e.start, e.end) == (610.0, 611.0) for e in result.events)
    assert result.usage.input_tokens == 3000


def test_a_failure_stops_the_scan_and_surfaces() -> None:
    with pytest.raises(QuotaExceededError):
        scan(StubJudge(fail_on_call=5))


def test_frame_clips_are_cut_sharper_than_video_clips(settings: Settings) -> None:
    frames = FrameScanner(StubJudge(), 0.5, FRAME_CHOICES).clip_spec(settings)
    video = SceneScanner(object(), []).clip_spec(settings)  # type: ignore[arg-type]
    assert (frames.height, frames.fps, frames.crf) == (720, 1.0, 20)
    assert video.height == settings.scan_height
    assert video.crf == 30


def test_the_scan_key_changes_with_the_threshold(settings: Settings) -> None:
    low = FrameScanner(StubJudge(), 0.1, FRAME_CHOICES).config_key(settings)
    assert low != FrameScanner(StubJudge(), 0.5, FRAME_CHOICES).config_key(settings)


def test_the_scan_key_changes_with_the_chosen_categories_too(settings: Settings) -> None:
    both = FrameScanner(StubJudge(), 0.5, FRAME_CHOICES).config_key(settings)
    only = FrameScanner(StubJudge(), 0.5, [FilterCategory.NUDITY]).config_key(settings)
    assert both != only


def test_only_the_chosen_categories_are_asked_about() -> None:
    names = [q.name for q in questions_for(3, [FilterCategory.NUDITY])]
    assert names == [NUDITY]
    names = [
        q.name for q in questions_for(1, [FilterCategory.SEXUAL_CONTENT, FilterCategory.VIOLENCE])
    ]
    assert names == [SEXUAL]  # the frame judge has no question for violence


def test_a_scan_asks_the_judge_nothing_about_unchosen_categories() -> None:
    judge = StubJudge(flag_frame="f_00011.jpg")
    result = FrameScanner(judge, 0.5, [FilterCategory.NUDITY]).scan_clip(
        Path("clip.mp4"), offset=0, media=FakeMediaTool()
    )
    assert {e.category for e in result.events} == {FilterCategory.NUDITY}


# --- choosing the scanner ------------------------------------------------------------------


def test_the_provider_name_picks_the_scanner(settings: Settings) -> None:
    video = build_scene_scanner(ProviderSet(settings), settings, [])
    assert isinstance(video, SceneScanner)
    frames_settings = settings.model_copy(update={"moderation_provider": "fake-frames"})
    assert isinstance(
        build_scene_scanner(ProviderSet(frames_settings), frames_settings, []), FrameScanner
    )


def test_an_unknown_provider_lists_both_kinds(settings: Settings) -> None:
    bad = settings.model_copy(update={"moderation_provider": "nope"})
    with pytest.raises(UnknownProviderError, match=r"gemini.*openai"):
        build_scene_scanner(ProviderSet(bad), bad, [])


def test_the_whole_pipeline_runs_with_the_frame_scanner(
    settings: Settings, source_file: Path
) -> None:
    frames_settings = settings.model_copy(update={"moderation_provider": "fake-frames"})
    container = build_container(frames_settings, media=FakeMediaTool())
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(filter_categories=FRAME_CHOICES))
    timeline = read_model(container.store.paths(manifest).visual_events, FilterTimeline)
    assert {e.category.value for e in timeline.events} == {"nudity", "sexual_content"}


def test_what_each_scanner_can_check_is_known_without_any_key(settings: Settings) -> None:
    assert scannable_categories(settings) == PICTURE_CATEGORIES
    frames_settings = settings.model_copy(update={"moderation_provider": "openai"})
    assert scannable_categories(frames_settings) == tuple(FRAME_CHOICES)


# --- the OpenAI connection -----------------------------------------------------------------


class FakeDecisions:
    def __init__(self, answers: list[object] | Exception) -> None:
        self.calls: list[dict[str, object]] = []
        self._answers = answers

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self._answers, Exception):
            raise self._answers
        return SimpleNamespace(
            answers=self._answers, usage=SimpleNamespace(input_tokens=1379, output_tokens=0)
        )


def judge_with(decisions: FakeDecisions) -> OpenAIFrameJudge:
    client = SimpleNamespace(decisions=decisions)
    return OpenAIFrameJudge(client=client, model="gpt-6-luna")  # type: ignore[arg-type]


def predicate(name: str, probability: float) -> object:
    return SimpleNamespace(type="predicate", name=name, probability=probability)


QUESTIONS = [FrameQuestion(name="nudity", instructions="Is there nudity?")]


def test_frames_and_questions_are_sent_and_answers_returned(tmp_path: Path) -> None:
    frame = tmp_path / "f.jpg"
    frame.write_bytes(b"jpegbytes")
    decisions = FakeDecisions([predicate("nudity", 0.8)])
    result = judge_with(decisions).judge([frame, frame], "two frames", QUESTIONS)

    assert result.probabilities == {"nudity": 0.8}
    assert result.usage.input_tokens == 1379
    (call,) = decisions.calls
    assert call["model"] == "gpt-6-luna"
    assert call["questions"] == [
        {"type": "predicate", "name": "nudity", "instructions": "Is there nudity?"}
    ]
    parts = call["input"][0]["content"]  # type: ignore[index]
    assert parts[0] == {"type": "input_text", "text": "two frames"}
    assert [p["type"] for p in parts[1:]] == ["input_image", "input_image"]
    assert parts[1]["image_url"].startswith("data:image/jpeg;base64,")


def test_a_refusal_is_a_clear_error(tmp_path: Path) -> None:
    frame = tmp_path / "f.jpg"
    frame.write_bytes(b"x")
    refusal = SimpleNamespace(type="refusal", name="nudity")
    with pytest.raises(ProviderError, match="declined"):
        judge_with(FakeDecisions([refusal])).judge([frame], "one", QUESTIONS)


def test_a_rate_limit_stops_with_the_retry_time(tmp_path: Path) -> None:
    frame = tmp_path / "f.jpg"
    frame.write_bytes(b"x")
    response = httpx2.Response(
        429,
        headers={"retry-after": "30"},
        request=httpx2.Request("POST", "https://api.openai.com"),
    )
    error = openai.RateLimitError("slow down", response=response, body=None)
    with pytest.raises(QuotaExceededError) as info:
        judge_with(FakeDecisions(error)).judge([frame], "one", QUESTIONS)
    assert info.value.retry_after_seconds == 30
    assert "30 s" in str(info.value)


def test_the_openai_key_is_required(settings: Settings) -> None:
    real = settings.model_copy(update={"moderation_provider": "openai"})
    with pytest.raises(Exception, match="OPENAI_API_KEY"):
        _ = ProviderSet(real).frame_judge
