import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from velvetdub.api.app import create_app
from velvetdub.container import Container
from velvetdub.domain.manifest import Manifest
from velvetdub.pipeline.context import ProcessOptions

CLIENT = {"x-velvetdub-client": "test"}


@pytest.fixture
def processed(container: Container, source_file: Path) -> Manifest:
    manifest = container.store.create("local", "Movie", source_file)
    container.process(manifest, ProcessOptions(subtitle_languages=["en", "es"]))
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
    assert ok.content == b"fake-audio"
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


def test_playback_resolves_filters_for_the_profile(client: TestClient, processed: Manifest) -> None:
    kids = client.get(f"{base(processed)}/playback", params={"profile": "kids"}).json()
    assert kids["profile"] == {"id": "kids", "name": "Kids (G)"}
    assert {f["category"] for f in kids["filters"]} == {"swearing", "violence"}
    assert {f["action"] for f in kids["filters"]} == {"mute", "skip"}
    assert kids["runtime_removed"] == 12.0  # the fake scan's 10 s, plus a second each side
    assert [t["id"] for t in kids["audio_tracks"]] == ["original"]
    assert {t["language"] for t in kids["subtitle_tracks"]} == {"en", "es"}
    assert kids["duration"] == 60.0

    # "language only" never skips scenes, and "family" ignores mild swearing
    lang = client.get(f"{base(processed)}/playback", params={"profile": "language_only"}).json()
    assert {f["action"] for f in lang["filters"]} == {"mute"}
    family = client.get(f"{base(processed)}/playback", params={"profile": "family"}).json()
    assert {f["category"] for f in family["filters"]} == {"violence"}


def test_unknown_profile_is_404(client: TestClient, processed: Manifest) -> None:
    assert client.get(f"{base(processed)}/playback", params={"profile": "nope"}).status_code == 404


def test_unprocessed_title_plays_with_no_filters(
    client: TestClient, container: Container, source_file: Path
) -> None:
    fresh = container.store.create("local", "Fresh", source_file)
    info = client.get(f"{base(fresh)}/playback").json()
    assert info["filters"] == [] and info["subtitle_tracks"] == []


def test_profiles_list(client: TestClient) -> None:
    names = [p["name"] for p in client.get("/api/profiles").json()]
    assert names == ["Kids (G)", "Family (PG)", "Teen", "Language only"]


# --- keep it in / review -----------------------------------------------------------------


def test_keeping_a_detection_in_removes_it_from_playback_but_not_review(
    client: TestClient, processed: Manifest
) -> None:
    kids = {"profile": "kids"}
    skip = next(
        f
        for f in client.get(f"{base(processed)}/playback", params=kids).json()["filters"]
        if f["action"] == "skip"
    )

    assert client.put(f"{base(processed)}/events/{skip['id']}/keep").json() == {
        "keep": [skip["id"]]
    }

    playback = client.get(f"{base(processed)}/playback", params=kids).json()
    assert skip["id"] not in [f["id"] for f in playback["filters"]]
    assert playback["runtime_removed"] == 0.0

    review = client.get(f"{base(processed)}/review", params=kids).json()
    row = next(f for f in review["filters"] if f["id"] == skip["id"])
    assert row["kept"] is True
    assert review["runtime_removed"] == 0.0

    client.delete(f"{base(processed)}/events/{skip['id']}/keep")
    again = client.get(f"{base(processed)}/playback", params=kids).json()
    assert skip["id"] in [f["id"] for f in again["filters"]]


# --- subtitles ---------------------------------------------------------------------------


def test_subtitles_are_masked_per_profile(client: TestClient, processed: Manifest) -> None:
    raw = client.get(f"{base(processed)}/subtitles/en.vtt").text
    assert "What the hell is that?" in raw

    kids = client.get(f"{base(processed)}/subtitles/en.vtt", params={"profile": "kids"}).text
    assert "What the **** is that?" in kids
    assert "Hello there, friend." in kids

    # the family preset allows mild swearing, so nothing is masked
    family = client.get(f"{base(processed)}/subtitles/en.vtt", params={"profile": "family"}).text
    assert "hell" in family


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
