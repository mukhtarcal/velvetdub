import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeMediaTool
from velvetdub.api.app import create_app
from velvetdub.container import Container
from velvetdub.domain.filtering import FilterCategory, FilterEvent, FilterTimeline, Severity
from velvetdub.domain.manifest import Manifest
from velvetdub.features.scene_filtering.categories import PICTURE_CATEGORIES
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.services.posters import PosterService
from velvetdub.storage.artifacts import read_model

CLIENT = {"x-velvetdub-client": "test"}
# Everything that can be chosen: the four picture categories and swearing.
EVERYTHING = [*PICTURE_CATEGORIES, FilterCategory.SWEARING]


@pytest.fixture
def processed(container: Container, source_file: Path) -> Manifest:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(
        manifest,
        ProcessOptions(subtitle_languages=["en", "es"], filter_categories=EVERYTHING),
    )
    return manifest


@pytest.fixture
def client(container: Container) -> TestClient:
    return TestClient(create_app(container), headers=CLIENT)


def base(manifest: Manifest) -> str:
    return f"/api/titles/{manifest.title_id}"


# --- request guard -----------------------------------------------------------------------


def test_unknown_host_is_refused(container: Container) -> None:
    rebinding = TestClient(create_app(container), base_url="http://evil.example")
    assert rebinding.get("/api/health").status_code == 403


def test_state_changing_requests_need_the_client_header(
    container: Container, processed: Manifest
) -> None:
    bare = TestClient(create_app(container))  # right host, no custom header
    assert bare.get("/api/health").status_code == 200
    assert bare.put(f"{base(processed)}/events/x/keep").status_code == 403


# --- media -------------------------------------------------------------------------------


def test_video_supports_range_requests(client: TestClient, processed: Manifest) -> None:
    resp = client.get(f"{base(processed)}/media/source", headers={"Range": "bytes=0-4"})
    assert resp.status_code == 206
    assert resp.content == b"fake-"
    assert resp.headers["content-range"].startswith("bytes 0-4/")


def test_audio_track_is_served_from_the_manifest(client: TestClient, processed: Manifest) -> None:
    ok = client.get(f"{base(processed)}/media/audio/original")
    assert ok.status_code == 200
    assert ok.content == b"fake-video"  # the film's own sound, straight from the film
    assert client.get(f"{base(processed)}/media/audio/nope").status_code == 404
    assert client.get(f"{base(processed)}/media/audio/..%2F..%2Fmanifest").status_code == 404


def test_other_users_media_is_not_found(container: Container, processed: Manifest) -> None:
    from starlette.requests import Request

    from velvetdub.auth.identity import IdentityProvider
    from velvetdub.domain.user import User

    class Someone(IdentityProvider):
        def current_user(self, request: Request) -> User:
            return User(id="intruder", display_name="x")

    container.identity = Someone()
    resp = TestClient(create_app(container), headers=CLIENT).get(f"{base(processed)}/media/source")
    assert resp.status_code == 404


# --- playback ----------------------------------------------------------------------------


def test_playback_acts_on_everything_that_was_found(
    client: TestClient, processed: Manifest
) -> None:
    info = client.get(f"{base(processed)}/playback").json()
    assert "profile" not in info
    assert {f["category"] for f in info["filters"]} == {"swearing", "violence"}
    assert {f["action"] for f in info["filters"]} == {"mute", "skip"}
    assert info["runtime_removed"] == 12.0  # the fake scan's 10 s, plus a second each side
    assert [t["id"] for t in info["audio_tracks"]] == ["original"]
    assert {t["language"] for t in info["subtitle_tracks"]} == {"en", "es"}
    assert all(t["url"].endswith("?mask=true") for t in info["subtitle_tracks"])
    assert info["duration"] == 60.0


def test_profiles_are_gone(client: TestClient, processed: Manifest) -> None:
    assert client.get("/api/profiles").status_code == 404


def test_unprocessed_title_plays_with_no_filters(
    client: TestClient, container: Container, source_file: Path
) -> None:
    fresh = container.store.create("local", "Fresh", source_file)
    info = client.get(f"{base(fresh)}/playback").json()
    assert info["filters"] == [] and info["subtitle_tracks"] == []


# --- keep it in / review -----------------------------------------------------------------


def test_keeping_a_detection_in_removes_it_from_playback_but_not_review(
    client: TestClient, processed: Manifest
) -> None:
    skip = next(
        f
        for f in client.get(f"{base(processed)}/playback").json()["filters"]
        if f["action"] == "skip"
    )

    assert client.put(f"{base(processed)}/events/{skip['id']}/keep").json() == {
        "keep": [skip["id"]]
    }

    playback = client.get(f"{base(processed)}/playback").json()
    assert skip["id"] not in [f["id"] for f in playback["filters"]]
    assert playback["runtime_removed"] == 0.0

    review = client.get(f"{base(processed)}/review").json()
    row = next(f for f in review["filters"] if f["id"] == skip["id"])
    assert row["kept"] is True
    assert review["runtime_removed"] == 0.0

    client.delete(f"{base(processed)}/events/{skip['id']}/keep")
    again = client.get(f"{base(processed)}/playback").json()
    assert skip["id"] in [f["id"] for f in again["filters"]]


# --- subtitles ---------------------------------------------------------------------------


def test_keeping_in_many_at_once_and_filtering_them_again(
    client: TestClient, processed: Manifest
) -> None:
    ids = [f["id"] for f in client.get(f"{base(processed)}/playback").json()["filters"]]
    assert len(ids) == 2

    kept = client.put(f"{base(processed)}/keep", json={"event_ids": ids, "keep": True}).json()
    assert sorted(kept["keep"]) == sorted(ids)
    assert client.get(f"{base(processed)}/playback").json()["filters"] == []
    review = client.get(f"{base(processed)}/review").json()
    assert all(f["kept"] for f in review["filters"])

    # keeping the same ones in again does not duplicate them
    again = client.put(f"{base(processed)}/keep", json={"event_ids": ids, "keep": True}).json()
    assert len(again["keep"]) == 2

    back = client.put(f"{base(processed)}/keep", json={"event_ids": ids[:1], "keep": False}).json()
    assert back["keep"] == ids[1:]
    assert [f["id"] for f in client.get(f"{base(processed)}/playback").json()["filters"]] == ids[:1]


def test_subtitles_are_masked_only_when_asked(client: TestClient, processed: Manifest) -> None:
    raw = client.get(f"{base(processed)}/subtitles/en.vtt").text
    assert "What the hell is that?" in raw

    masked = client.get(f"{base(processed)}/subtitles/en.vtt", params={"mask": True}).text
    assert "What the **** is that?" in masked
    assert "Hello there, friend." in masked

    # a word you chose to keep in is no longer masked
    word = next(f for f in client.get(f"{base(processed)}/playback").json()["filters"] if f["text"])
    client.put(f"{base(processed)}/events/{word['id']}/keep")
    kept = client.get(f"{base(processed)}/subtitles/en.vtt", params={"mask": True}).text
    assert "hell" in kept


def test_srt_export_and_download_header(client: TestClient, processed: Manifest) -> None:
    resp = client.get(f"{base(processed)}/subtitles/es.srt", params={"download": True})
    assert resp.status_code == 200
    assert resp.text.startswith("1\n00:00:01,000 --> 00:00:03,000\n[es] Hello there, friend.")
    assert 'filename="es.srt"' in resp.headers["content-disposition"]


def test_bad_subtitle_requests(client: TestClient, processed: Manifest) -> None:
    assert client.get(f"{base(processed)}/subtitles/fr.vtt").status_code == 404
    assert client.get(f"{base(processed)}/subtitles/en.txt").status_code == 404


def test_import_replaces_a_languages_subtitles(client: TestClient, processed: Manifest) -> None:
    content = "1\n00:00:00,500 --> 00:00:01,500\nMy own line\n"
    assert client.put(
        f"{base(processed)}/subtitles/de/import", json={"content": content}
    ).json() == {"lines": 1}
    assert "My own line" in client.get(f"{base(processed)}/subtitles/de.vtt").text
    assert "de" in {
        t["language"] for t in client.get(f"{base(processed)}/playback").json()["subtitle_tracks"]
    }


def test_import_rejects_garbage_and_unsafe_names(client: TestClient, processed: Manifest) -> None:
    bad = client.put(f"{base(processed)}/subtitles/de/import", json={"content": "not subtitles"})
    assert bad.status_code == 422
    unsafe = client.put(
        f"{base(processed)}/subtitles/..%2Fx/import",
        json={"content": "1\n00:00:00,000 --> 00:00:01,000\nx"},
    )
    assert unsafe.status_code in (404, 422)


# --- script editor -----------------------------------------------------------------------


def test_script_shows_original_and_translation_and_edits_persist(
    client: TestClient, processed: Manifest
) -> None:
    script = client.get(f"{base(processed)}/script/es").json()
    assert script[0]["original"] == "Hello there, friend."
    assert script[0]["text"] == "[es] Hello there, friend."

    edit = client.put(f"{base(processed)}/script/es/s0", json={"text": "Hola, amigo."})
    assert edit.status_code == 204
    assert client.get(f"{base(processed)}/script/es").json()[0]["text"] == "Hola, amigo."
    assert "Hola, amigo." in client.get(f"{base(processed)}/subtitles/es.vtt").text
    assert "00:00:01.000 --> 00:00:03.000" in client.get(f"{base(processed)}/subtitles/es.vtt").text


def test_editing_an_unknown_line_is_404(client: TestClient, processed: Manifest) -> None:
    assert client.put(f"{base(processed)}/script/es/nope", json={"text": "x"}).status_code == 404


# --- corrections -------------------------------------------------------------------------


def test_corrections_are_saved_per_title(client: TestClient, processed: Manifest) -> None:
    body = {"kind": "missed", "at_seconds": 41.5, "category": "violence", "note": "punch"}
    saved = client.post(f"{base(processed)}/corrections", json=body)
    assert saved.status_code == 201 and saved.json()["id"] == 1
    listed = client.get(f"{base(processed)}/corrections").json()
    assert [(c["kind"], c["at_seconds"]) for c in listed] == [("missed", 41.5)]
    assert (
        client.post(f"{base(processed)}/corrections", json={**body, "kind": "weird"}).status_code
        == 422
    )


# --- upload and processing ---------------------------------------------------------------


def wait_for(client: TestClient, title_id: str, *statuses: str) -> dict[str, object]:
    for _ in range(100):
        state = client.get(f"/api/titles/{title_id}/progress").json()
        if state["status"] in statuses:
            return state  # type: ignore[no-any-return]
        time.sleep(0.05)
    raise AssertionError(f"job never reached {statuses}: {state}")


def test_upload_then_process_in_the_background(client: TestClient, container: Container) -> None:
    uploaded = client.post(
        "/api/titles",
        params={"name": "Uploaded film", "filename": "film.MP4"},
        content=b"x" * 5000,
    )
    assert uploaded.status_code == 201
    title_id = uploaded.json()["id"]
    assert not list((container.settings.data_path / "uploads").glob("*"))  # staging is cleaned up

    started = client.post(f"/api/titles/{title_id}/process", json={"subtitle_languages": ["en"]})
    assert started.status_code == 202
    assert set(started.json()["stages"]) >= {"extract_audio", "transcribe", "subtitles"}

    done = wait_for(client, title_id, "done", "failed")
    assert done["status"] == "done"
    assert set(done["stages"].values()) == {"done"}  # type: ignore[attr-defined]
    assert client.get(f"/api/titles/{title_id}/subtitles/en.vtt").status_code == 200


def test_upload_rejects_non_video_and_empty_files(client: TestClient, container: Container) -> None:
    wrong = client.post("/api/titles", params={"name": "x", "filename": "notes.txt"}, content=b"hi")
    assert wrong.status_code == 400
    empty = client.post("/api/titles", params={"name": "x", "filename": "a.mp4"}, content=b"")
    assert empty.status_code == 400
    assert client.get("/api/titles").json() == []
    assert not list((container.settings.data_path / "uploads").glob("*"))


def test_failed_stage_is_reported_in_progress(client: TestClient, container: Container) -> None:
    container.settings.transcription_provider = "assemblyai"
    container.settings.assemblyai_api_key = None
    title_id = client.post(
        "/api/titles", params={"name": "x", "filename": "a.mp4"}, content=b"data"
    ).json()["id"]
    client.post(f"/api/titles/{title_id}/process", json={"subtitle_languages": ["en"]})

    state = wait_for(client, title_id, "failed", "done")
    assert state["status"] == "failed"
    assert "ASSEMBLYAI_API_KEY" in str(state["error"])
    assert state["stages"]["transcribe"] == "failed"  # type: ignore[index]


def test_progress_for_unknown_or_idle_titles_is_404(
    client: TestClient, processed: Manifest
) -> None:
    assert client.get("/api/titles/nope/progress").status_code == 404
    assert client.get(f"{base(processed)}/progress").status_code == 404  # never queued via the API


# --- library poster ----------------------------------------------------------------------


def test_the_poster_comes_from_a_moment_clear_of_every_scene_found(
    client: TestClient, processed: Manifest, media: FakeMediaTool
) -> None:
    first = client.get(f"{base(processed)}/media/poster")
    assert first.status_code == 200
    assert first.headers["content-type"] == "image/jpeg"
    assert first.content == b"jpeg"
    # The fake scan found violence at 10-20 s of the 60 s film. 6, 12, 18, 24 and 30 s are all
    # within ten seconds of it, so 36 s is the first moment clear of it.
    assert media.poster_calls == [36.0]

    assert client.get(f"{base(processed)}/media/poster").status_code == 200
    assert media.poster_calls == [36.0]  # the second request reused the saved picture


def test_there_is_no_poster_before_the_film_has_been_scanned(
    client: TestClient, container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    fresh = container.store.create("local", "Fresh", source_file)
    assert client.get(f"{base(fresh)}/media/poster").status_code == 404
    assert media.poster_calls == []  # no frame was taken, so none could show a filtered scene


def test_a_poster_is_made_from_ten_percent_in_when_no_scene_was_found(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    manifest = container.store.create("local", "Quiet", source_file)
    container.process(manifest, ProcessOptions())  # no filters chosen, so no scenes
    client = TestClient(create_app(container), headers=CLIENT)
    assert client.get(f"{base(manifest)}/media/poster").status_code == 200
    assert media.poster_calls == [6.0]


def test_no_poster_when_scenes_cover_the_whole_film(
    container: Container, processed: Manifest, media: FakeMediaTool
) -> None:
    paths = container.store.paths(processed)
    paths.filters.write_text(
        FilterTimeline(
            events=[
                FilterEvent(
                    id="all",
                    category=FilterCategory.NUDITY,
                    severity=Severity.STRONG,
                    start=0,
                    end=60,
                    source="t",
                )
            ]
        ).model_dump_json()
    )
    client = TestClient(create_app(container), headers=CLIENT)
    assert client.get(f"{base(processed)}/media/poster").status_code == 404
    assert media.poster_calls == []


def test_spoken_words_do_not_keep_the_poster_away(
    container: Container, source_file: Path, media: FakeMediaTool
) -> None:
    # The fake transcript has swearing at 4-6 s; only picture scenes matter for the poster.
    manifest = container.store.create("local", "Words", source_file)
    container.process(manifest, ProcessOptions(filter_categories=[FilterCategory.SWEARING]))
    assert any(
        e.category is FilterCategory.SWEARING
        for e in read_model(container.store.paths(manifest).filters, FilterTimeline).events
    )
    TestClient(create_app(container), headers=CLIENT).get(f"{base(manifest)}/media/poster")
    assert media.poster_calls == [6.0]


def test_a_failed_poster_is_a_404_and_leaves_nothing_behind(
    client: TestClient, container: Container, processed: Manifest
) -> None:
    class Broken(FakeMediaTool):
        def extract_poster(self, source: Path, dest: Path, *, at_seconds: float) -> None:
            dest.write_bytes(b"half")
            raise subprocess.CalledProcessError(1, "ffmpeg")

    container.posters = PosterService(container.store, Broken())
    assert client.get(f"{base(processed)}/media/poster").status_code == 404
    folder = container.store.paths(processed).root
    assert not list(folder.glob("poster*"))


def test_rebuilding_the_filters_drops_the_saved_poster(
    client: TestClient, container: Container, processed: Manifest, media: FakeMediaTool
) -> None:
    client.get(f"{base(processed)}/media/poster")
    assert container.store.paths(processed).poster.exists()

    container.settings.moderation_model = "another-model"  # re-runs the scan, then the merge
    container.providers.__dict__.pop("video_analyzer", None)
    container.process(
        processed,
        ProcessOptions(filter_categories=EVERYTHING, subtitle_languages=["en", "es"]),
    )
    assert not container.store.paths(processed).poster.exists()


def test_other_users_poster_is_not_found(container: Container, processed: Manifest) -> None:
    from starlette.requests import Request

    from velvetdub.auth.identity import IdentityProvider
    from velvetdub.domain.user import User

    class Someone(IdentityProvider):
        def current_user(self, request: Request) -> User:
            return User(id="intruder", display_name="x")

    container.identity = Someone()
    other = TestClient(create_app(container), headers=CLIENT)
    assert other.get(f"{base(processed)}/media/poster").status_code == 404
