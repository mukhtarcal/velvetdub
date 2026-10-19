import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from tests.conftest import FakeMediaTool
from velvetdub.api.app import create_app
from velvetdub.auth.identity import IdentityProvider
from velvetdub.config.settings import Settings
from velvetdub.container import Container, build_container
from velvetdub.domain.user import User


def test_health(container: Container) -> None:
    client = TestClient(create_app(container))
    assert client.get("/api/health").json()["status"] == "ok"


def test_titles_list_and_detail(container: Container, source_file: Path) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    client = TestClient(create_app(container))

    listing = client.get("/api/titles").json()
    assert [t["id"] for t in listing] == [manifest.title_id]
    assert client.get(f"/api/titles/{manifest.title_id}").json()["name"] == "Movie"


def test_unknown_title_is_404(container: Container) -> None:
    client = TestClient(create_app(container))
    assert client.get("/api/titles/doesnotexist").status_code == 404


def test_swapping_identity_isolates_users(container: Container, source_file: Path) -> None:
    """Shows the multi-user seam: only the IdentityProvider changes."""

    class HeaderIdentity(IdentityProvider):
        def current_user(self, request: Request) -> User:
            return User(id=request.headers["x-user"], display_name="test")

    container.identity = HeaderIdentity()
    manifest = container.store.create("alice", "Alice's film", source_file)
    client = TestClient(create_app(container))

    assert len(client.get("/api/titles", headers={"x-user": "alice"}).json()) == 1
    assert client.get("/api/titles", headers={"x-user": "bob"}).json() == []
    resp = client.get(f"/api/titles/{manifest.title_id}", headers={"x-user": "bob"})
    assert resp.status_code == 404


@pytest.mark.parametrize("path", ["/api/titles/../../etc/passwd", "/api/titles/%2e%2e"])
def test_path_traversal_is_not_served(container: Container, path: str) -> None:
    client = TestClient(create_app(container))
    assert client.get(path).status_code in (404, 422)


# --- choosing filters and subtitles ----------------------------------------------------------

CLIENT = {"x-velvetdub-client": "test"}


def wait_until_finished(client: TestClient, title_id: str) -> dict[str, object]:
    for _ in range(100):
        state = client.get(f"/api/titles/{title_id}/progress").json()
        if state["status"] in ("done", "failed"):
            return state  # type: ignore[no-any-return]
        time.sleep(0.05)
    raise AssertionError("processing did not finish")


def test_a_title_can_be_processed_with_no_subtitles_and_no_filters(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    client = TestClient(create_app(container), headers=CLIENT)

    response = client.post(f"/api/titles/{manifest.title_id}/process", json={})
    assert response.status_code == 202
    assert wait_until_finished(client, manifest.title_id)["status"] == "done"

    title = client.get("/api/titles").json()[0]
    assert title["choices"] == {
        "filter_categories": [],
        "subtitle_languages": [],
        "dub_languages": [],
    }
    assert title["scanned_categories"] == []
    assert client.get(f"/api/titles/{manifest.title_id}").json()["subtitle_tracks"] == []


def test_the_chosen_filters_are_scanned_and_listed_on_the_title(
    container: Container, source_file: Path
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    client = TestClient(create_app(container), headers=CLIENT)

    body = {"subtitle_languages": ["en"], "filter_categories": ["violence", "nudity"]}
    assert client.post(f"/api/titles/{manifest.title_id}/process", json=body).status_code == 202
    wait_until_finished(client, manifest.title_id)

    title = client.get("/api/titles").json()[0]
    assert title["choices"]["filter_categories"] == ["nudity", "violence"]
    assert title["scanned_categories"] == ["nudity", "violence"]
    review = client.get(f"/api/titles/{manifest.title_id}/review").json()
    assert review["scanned_categories"] == ["nudity", "violence"]


@pytest.mark.parametrize("category", ["drugs_and_drinking", "blasphemy", "nonsense"])
def test_only_the_offered_filters_can_be_chosen(
    container: Container, source_file: Path, category: str
) -> None:
    manifest = container.store.create("local", "Movie", source_file)
    client = TestClient(create_app(container), headers=CLIENT)
    body = {"filter_categories": [category]}
    assert client.post(f"/api/titles/{manifest.title_id}/process", json=body).status_code == 422


def test_a_filter_the_scanner_cannot_check_is_refused_in_plain_words(
    settings: Settings, source_file: Path, media: FakeMediaTool
) -> None:
    frames = settings.model_copy(update={"moderation_provider": "fake-frames"})
    container = build_container(frames, media=media)
    manifest = container.store.create("local", "Movie", source_file)
    client = TestClient(create_app(container), headers=CLIENT)

    body = {"filter_categories": ["nudity", "violence", "scary_scenes"]}
    response = client.post(f"/api/titles/{manifest.title_id}/process", json=body)
    assert response.status_code == 422
    assert response.json()["detail"] == "This scanner can't check for scary scenes or violence."

    ok = client.post(
        f"/api/titles/{manifest.title_id}/process", json={"filter_categories": ["nudity"]}
    )
    assert ok.status_code == 202


def test_capabilities_say_what_the_scanner_can_check(
    settings: Settings, media: FakeMediaTool
) -> None:
    video = TestClient(create_app(build_container(settings, media=media)))
    assert video.get("/api/capabilities").json()["scan_categories"] == [
        "nudity",
        "sexual_content",
        "scary_scenes",
        "violence",
    ]
    frames = settings.model_copy(update={"moderation_provider": "fake-frames"})
    frame_client = TestClient(create_app(build_container(frames, media=media)))
    assert frame_client.get("/api/capabilities").json()["scan_categories"] == [
        "nudity",
        "sexual_content",
    ]
