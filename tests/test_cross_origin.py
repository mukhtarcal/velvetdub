"""The browser sends a film straight to the API, which is a cross-origin request. Only the web
app's own addresses are approved for it, and nothing else about the guard is loosened."""

from fastapi.testclient import TestClient

from velvetdub.api.app import create_app
from velvetdub.container import Container

APP = "http://127.0.0.1:5273"
ELSEWHERE = "https://evil.example"
CLIENT = {"x-velvetdub-client": "web"}
UPLOAD = {"name": "Film", "filename": "film.mp4"}


def preflight(client: TestClient, origin: str, method: str = "POST") -> dict[str, str]:
    response = client.options(
        "/api/titles",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "x-velvetdub-client,content-type",
        },
    )
    return {"status": str(response.status_code), **response.headers}


def test_the_web_app_may_ask_to_send_an_upload_with_the_custom_header(container: Container) -> None:
    reply = preflight(TestClient(create_app(container)), APP)
    assert reply["status"] == "200"
    assert reply["access-control-allow-origin"] == APP
    assert "x-velvetdub-client" in reply["access-control-allow-headers"].lower()
    assert reply["access-control-allow-methods"] == "POST"


def test_localhost_is_approved_too_since_the_page_may_be_opened_either_way(
    container: Container,
) -> None:
    reply = preflight(TestClient(create_app(container)), "http://localhost:5273")
    assert reply["access-control-allow-origin"] == "http://localhost:5273"


def test_any_other_page_is_refused_so_it_cannot_add_the_custom_header(container: Container) -> None:
    reply = preflight(TestClient(create_app(container)), ELSEWHERE)
    assert reply["status"] == "400"
    assert "access-control-allow-origin" not in reply


def test_even_the_web_app_may_only_post_directly_the_rest_goes_through_its_proxy(
    container: Container,
) -> None:
    client = TestClient(create_app(container))
    for method in ("PUT", "DELETE"):
        reply = preflight(client, APP, method)
        assert reply["status"] == "400", method


def test_an_upload_from_the_web_app_works_and_is_readable_by_it(container: Container) -> None:
    client = TestClient(create_app(container), headers=CLIENT)
    response = client.post(
        "/api/titles", params=UPLOAD, content=b"x" * 2000, headers={"Origin": APP}
    )
    assert response.status_code == 201
    assert response.headers["access-control-allow-origin"] == APP


def test_a_post_from_another_page_is_still_stopped_by_the_guard(container: Container) -> None:
    client = TestClient(create_app(container))
    # No custom header, as a cross-site page without approval would be.
    response = client.post(
        "/api/titles", params=UPLOAD, content=b"x" * 2000, headers={"Origin": ELSEWHERE}
    )
    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers
    assert container.store.list("local") == []  # nothing was stored


def test_another_page_gets_no_permission_to_read_the_answer_even_with_the_header(
    container: Container,
) -> None:
    client = TestClient(create_app(container), headers=CLIENT)
    response = client.get("/api/titles", headers={"Origin": ELSEWHERE})
    assert "access-control-allow-origin" not in response.headers
