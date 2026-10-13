import tempfile
from pathlib import Path

import pytest
from pydantic import BaseModel

from tests.conftest import FakeMediaTool
from velvetdub.config.settings import Settings
from velvetdub.container import Container, build_container
from velvetdub.domain.filtering import FilterCategory, FilterTimeline
from velvetdub.domain.manifest import StageStatus
from velvetdub.domain.usage import TokenUsage
from velvetdub.errors import QuotaExceededError, StageFailedError
from velvetdub.media.tools import ScanClip
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.pipeline.observer import NullObserver
from velvetdub.pipeline.stages.visual_scan import ScanUsage
from velvetdub.providers.fake import FakeVideoAnalyzer
from velvetdub.storage.artifacts import read_model


class RecordingObserver(NullObserver):
    def __init__(self) -> None:
        self.started: list[str] = []
        self.skipped: list[str] = []

    def stage_started(self, stage: str) -> None:
        self.started.append(stage)

    def stage_skipped(self, stage: str) -> None:
        self.skipped.append(stage)


def test_full_run_produces_all_artifacts(container: Container, source_file: Path) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(subtitle_languages=["en", "es"]))

    paths = container.store.paths(manifest)
    for artifact in (
        paths.original_audio,
        paths.transcript,
        paths.visual_events,
        paths.filters,
        paths.translation("en"),
        paths.translation("es"),
        paths.subtitles("en"),
        paths.subtitles("es"),
    ):
        assert artifact.exists(), artifact

    assert all(r.status is StageStatus.DONE for r in manifest.stages.values())
    assert {t.language for t in manifest.subtitle_tracks} == {"en", "es"}
    assert [t.id for t in manifest.audio_tracks] == ["original"]

    vtt = paths.subtitles("es").read_text()
    assert vtt.startswith("WEBVTT")
    assert "00:00:01.000 --> 00:00:03.000" in vtt
    assert "[es] Hello there, friend." in vtt


def test_filters_merge_visual_and_spoken_detections(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions())

    timeline = read_model(container.store.paths(manifest).filters, FilterTimeline)
    categories = [e.category for e in timeline.events]
    assert FilterCategory.SWEARING in categories  # "hell" from the word list
    assert FilterCategory.VIOLENCE in categories  # from the fake visual scan
    assert timeline.events == timeline.sorted_events()


def test_rerun_skips_finished_stages(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions())

    observer = RecordingObserver()
    container.process(manifest, ProcessOptions(), observer)

    assert observer.started == []
    assert len(observer.skipped) == 6
    assert media.extract_calls == 1


def test_adding_a_language_reruns_only_dependent_stages(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(subtitle_languages=["en"]))

    observer = RecordingObserver()
    container.process(manifest, ProcessOptions(subtitle_languages=["en", "es"]), observer)

    assert observer.started == ["translate", "subtitles"]
    assert set(observer.skipped) == {"extract_audio", "transcribe", "visual_scan", "build_filters"}


def test_changing_the_model_invalidates_that_stage(container: Container, source_file: Path) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions())

    container.providers.__dict__.pop("video_analyzer")  # drop the cached provider
    container.settings.moderation_model = "another-model"
    observer = RecordingObserver()
    container.process(manifest, ProcessOptions(), observer)

    # The scan re-runs with the new model, and the filter merge that consumes it follows.
    assert observer.started == ["visual_scan", "build_filters"]
    assert set(observer.skipped) == {"extract_audio", "transcribe", "translate", "subtitles"}


def test_failed_stage_is_recorded_and_resumable(container: Container, source_file: Path) -> None:
    container.settings.transcription_provider = "assemblyai"
    container.settings.assemblyai_api_key = None
    manifest = container.store.create("local", "Movie", source_file)

    with pytest.raises(StageFailedError) as info:
        container.process(manifest, ProcessOptions())

    assert info.value.stage == "transcribe"
    assert manifest.stages["extract_audio"].status is StageStatus.DONE
    assert manifest.stages["transcribe"].status is StageStatus.FAILED
    assert "ASSEMBLYAI_API_KEY" in (manifest.stages["transcribe"].error or "")


class TwoClipMedia(FakeMediaTool):
    """A long film cut into two clips, the second starting 10 minutes in."""

    def make_scan_clips(
        self,
        source: Path,
        out_dir: Path,
        *,
        clip_seconds: int,
        fps: float,
        height: int,
        crf: int = 30,
    ) -> list[ScanClip]:
        out_dir.mkdir(parents=True, exist_ok=True)
        clips = []
        for index, offset in enumerate((0.0, 600.0)):
            path = out_dir / f"clip_{index}.mp4"
            path.write_bytes(b"clip")
            clips.append(ScanClip(path=path, offset=offset, duration=600.0))
        return clips


def test_visual_scan_places_each_clips_detections_on_the_film_timeline(
    settings: Settings, source_file: Path
) -> None:
    container = build_container(settings, media=TwoClipMedia())
    manifest = container.store.create("local", "Long film", source_file)
    container.process(manifest, ProcessOptions())

    timeline = read_model(container.store.paths(manifest).visual_events, FilterTimeline)
    assert [(e.id, e.start, e.end) for e in timeline.events] == [
        ("vis-0-0", 10.0, 20.0),
        ("vis-600-0", 610.0, 620.0),
    ]


def test_scan_clips_are_not_left_on_disk(container: Container, source_file: Path) -> None:
    before = set(Path(tempfile.gettempdir()).glob("vd-scan-*"))
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions())
    assert set(Path(tempfile.gettempdir()).glob("vd-scan-*")) == before


class FlakyAnalyzer(FakeVideoAnalyzer):
    """Fails on its `fail_on`th call until `heal()` is called; counts calls that succeeded."""

    def __init__(self, fail_on: int) -> None:
        super().__init__()
        self.fail_on = fail_on
        self.calls = 0
        self.succeeded = 0

    def heal(self) -> None:
        self.fail_on = -1

    def analyze_clip[T: BaseModel](self, clip_path: Path, instructions: str, schema: type[T]) -> T:
        self.calls += 1
        if self.calls == self.fail_on:
            raise QuotaExceededError("limit used up", retry_after_seconds=9000)
        self.succeeded += 1
        self.last_usage = TokenUsage(input_tokens=100, output_tokens=5)
        return super().analyze_clip(clip_path, instructions, schema)


def test_stopped_scan_resumes_at_the_failed_clip_and_records_usage(
    settings: Settings, source_file: Path
) -> None:
    analyzer = FlakyAnalyzer(fail_on=2)
    container = build_container(settings, media=TwoClipMedia())
    container.providers.video_analyzer = analyzer
    manifest = container.store.create("local", "Long film", source_file)

    with pytest.raises(StageFailedError):
        container.process(manifest, ProcessOptions())
    assert analyzer.succeeded == 1
    assert "limit used up" in (manifest.stages["visual_scan"].error or "")

    analyzer.heal()
    container.process(manifest, ProcessOptions())
    assert analyzer.succeeded == 2  # the first clip was not paid for again

    paths = container.store.paths(manifest)
    timeline = read_model(paths.visual_events, FilterTimeline)
    assert [e.id for e in timeline.events] == ["vis-0-0", "vis-600-0"]
    usage = read_model(paths.visual_usage, ScanUsage)
    assert (usage.clips, usage.input_tokens, usage.output_tokens) == (2, 200, 10)
