"""Only what is chosen is run. A film with nothing chosen is just stored: no transcription, no
picture scan, no translation, no voices, and no keys needed."""

from pathlib import Path

from fastapi.testclient import TestClient

from tests.conftest import FakeMediaTool
from tests.test_api import CLIENT, wait_until_finished
from tests.test_pipeline import DUB_STAGES, RecordingObserver
from velvetdub.api.app import create_app
from velvetdub.container import Container
from velvetdub.domain.filtering import FilterCategory, FilterTimeline
from velvetdub.domain.manifest import StageStatus
from velvetdub.domain.transcript import Transcript
from velvetdub.features.scene_filtering.categories import PICTURE_CATEGORIES
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.providers.fake import FakeTranscriber
from velvetdub.storage.artifacts import read_model

SWEARING = [FilterCategory.SWEARING]


class CountingTranscriber(FakeTranscriber):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[Path] = []

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        self.calls.append(audio_path)
        return super().transcribe(audio_path, language)


def counting(container: Container) -> CountingTranscriber:
    transcriber = CountingTranscriber()
    container.providers.transcriber = transcriber
    return transcriber


def test_with_nothing_chosen_no_service_is_touched_and_no_key_is_needed(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    # Every real service, with no keys set: any attempt to use one would fail the run.
    container.settings = container.settings.model_copy(
        update={
            "transcription_provider": "assemblyai",
            "translation_provider": "anthropic",
            "moderation_provider": "gemini",
            "tts_provider": "cartesia",
            "separation_provider": "demucs",
        }
    )
    container.providers = type(container.providers)(container.settings)
    manifest = container.store.create("local", "Movie", source_file)

    container.process(manifest, ProcessOptions())

    paths = container.store.paths(manifest)
    assert all(r.status is StageStatus.DONE for r in manifest.stages.values())
    assert media.extract_calls == 0  # not even the audio is pulled out
    assert not paths.original_audio.exists() and not paths.transcript.exists()
    assert not paths.dub_stems.exists()
    assert read_model(paths.filters, FilterTimeline).events == []
    # What the player and library need is still there.
    assert manifest.duration == 60.0
    assert [t.id for t in manifest.audio_tracks] == ["original"]
    assert manifest.subtitle_tracks == []


def test_a_second_run_with_nothing_chosen_does_nothing(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions())
    observer = RecordingObserver()
    container.process(manifest, ProcessOptions(), observer)
    assert observer.started == []


def test_swearing_alone_transcribes_and_finds_the_words_and_nothing_else(
    container: Container, source_file: Path
) -> None:
    transcriber = counting(container)
    manifest = container.store.create("local", "Movie", source_file)

    container.process(manifest, ProcessOptions(filter_categories=SWEARING))

    paths = container.store.paths(manifest)
    assert len(transcriber.calls) == 1
    events = read_model(paths.filters, FilterTimeline).events
    assert [e.category for e in events] == [FilterCategory.SWEARING]
    assert manifest.swearing_checked is True
    assert manifest.scanned_categories == []  # no picture scan was asked for
    assert manifest.choices is not None and manifest.choices.filter_categories == SWEARING
    assert manifest.subtitle_tracks == [] and not paths.translation("es").exists()


def test_subtitles_alone_transcribe_but_do_not_look_for_swearing(
    container: Container, source_file: Path
) -> None:
    transcriber = counting(container)
    manifest = container.store.create("local", "Movie", source_file)

    container.process(manifest, ProcessOptions(subtitle_languages=["es"]))

    paths = container.store.paths(manifest)
    assert len(transcriber.calls) == 1
    assert [t.language for t in manifest.subtitle_tracks] == ["es"]
    assert read_model(paths.filters, FilterTimeline).events == []  # "hell" is not looked for
    assert manifest.swearing_checked is False


def test_a_dub_alone_never_transcribes_the_films_own_mix(
    container: Container, source_file: Path
) -> None:
    transcriber = counting(container)
    manifest = container.store.create("local", "Movie", source_file)

    container.process(manifest, ProcessOptions(dub_languages=["es"]))

    paths = container.store.paths(manifest)
    assert [call.name for call in transcriber.calls] == ["dialogue.m4a"]  # the separated voices
    assert not paths.original_audio.exists() and not paths.transcript.exists()
    assert {t.id for t in manifest.audio_tracks} == {"original", "dub-es"}
    assert read_model(paths.filters, FilterTimeline).events == []


def test_the_picture_scan_alone_needs_no_transcript(
    container: Container, source_file: Path
) -> None:
    transcriber = counting(container)
    manifest = container.store.create("local", "Movie", source_file)

    container.process(manifest, ProcessOptions(filter_categories=list(PICTURE_CATEGORIES)))

    paths = container.store.paths(manifest)
    assert transcriber.calls == []
    events = read_model(paths.filters, FilterTimeline).events
    assert {e.category for e in events} == {FilterCategory.VIOLENCE}  # the fake scan's finding
    assert manifest.swearing_checked is False


def test_adding_swearing_later_only_redoes_the_merge(
    container: Container, source_file: Path
) -> None:
    transcriber = counting(container)
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(subtitle_languages=["en"]))

    observer = RecordingObserver()
    container.process(
        manifest,
        ProcessOptions(subtitle_languages=["en"], filter_categories=SWEARING),
        observer,
    )

    assert observer.started == ["build_filters"]  # the transcript was already there
    assert len(transcriber.calls) == 1
    events = read_model(container.store.paths(manifest).filters, FilterTimeline).events
    assert [e.category for e in events] == [FilterCategory.SWEARING]
    assert manifest.swearing_checked is True


def test_adding_subtitles_to_a_title_that_had_nothing_does_the_missing_work(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions())
    assert media.extract_calls == 0

    observer = RecordingObserver()
    container.process(manifest, ProcessOptions(subtitle_languages=["es"]), observer)

    assert observer.started == ["extract_audio", "transcribe", "translate", "subtitles"]
    assert set(observer.skipped) == {"visual_scan", "build_filters"} | DUB_STAGES
    assert media.extract_calls == 1


def test_turning_everything_off_again_runs_nothing_new(
    container: Container, source_file: Path
) -> None:
    transcriber = counting(container)
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(filter_categories=SWEARING))
    container.process(manifest, ProcessOptions())
    assert len(transcriber.calls) == 1  # never transcribed again, and no longer needed


# --- through the API -------------------------------------------------------------------------


def test_swearing_can_be_chosen_through_the_api_and_is_reported_on_review(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    client = TestClient(create_app(container), headers=CLIENT)

    body = {"filter_categories": ["swearing", "violence"]}
    assert client.post(f"/api/titles/{manifest.title_id}/process", json=body).status_code == 202
    assert wait_until_finished(client, manifest.title_id)["status"] == "done"

    title = client.get("/api/titles").json()[0]
    assert title["choices"]["filter_categories"] == ["violence", "swearing"]
    review = client.get(f"/api/titles/{manifest.title_id}/review").json()
    assert review["swearing_checked"] is True
    assert review["scanned_categories"] == ["violence"]


def test_review_says_swearing_was_not_looked_for_when_it_was_not_chosen(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    client = TestClient(create_app(container), headers=CLIENT)
    client.post(f"/api/titles/{manifest.title_id}/process", json={})
    wait_until_finished(client, manifest.title_id)
    review = client.get(f"/api/titles/{manifest.title_id}/review").json()
    assert review["swearing_checked"] is False


def test_a_title_made_before_swearing_was_a_choice_reads_as_checked(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Old", source_file)
    container.process(manifest, ProcessOptions(filter_categories=SWEARING))
    manifest.swearing_checked = None  # as in a manifest written before this existed
    container.store.save(manifest)
    client = TestClient(create_app(container))
    review = client.get(f"/api/titles/{manifest.title_id}/review").json()
    assert review["swearing_checked"] is None  # the page reads this as "checked"
