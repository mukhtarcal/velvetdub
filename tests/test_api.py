from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from velvetdub.api.app import create_app
from velvetdub.auth.identity import IdentityProvider
from velvetdub.container import Container
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
