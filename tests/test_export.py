"""The cleaned copy: planning the edit, the ffmpeg graph, the background job, and the API."""

import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient

from tests.conftest import FakeMediaTool
from velvetdub.api.app import create_app
from velvetdub.container import Container
from velvetdub.domain.export import (
    MUTE_LEAD_SECONDS,
    MUTE_TAIL_SECONDS,
    EditPlan,
    plan_edit,
)
from velvetdub.domain.filtering import (
    FilterAction,
    FilterCategory,
    FilterEvent,
    ResolvedFilter,
    Severity,
)
from velvetdub.domain.manifest import Manifest
from velvetdub.features.scene_filtering.categories import PICTURE_CATEGORIES
from velvetdub.media.tools import FFmpegMediaTool, cleaned_filter_script
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.services.exports import ExportStatus, download_name

CLIENT = {"x-velvetdub-client": "test"}


def cut(start: float, end: float, action: FilterAction = FilterAction.SKIP) -> ResolvedFilter:
    event = FilterEvent(
        id=f"e{start}",
        category=FilterCategory.SWEARING if action is FilterAction.MUTE else FilterCategory.NUDITY,
        severity=Severity.STRONG,
        start=start,
        end=end,
        source="t",
    )
    return ResolvedFilter(event=event, action=action)


# --- planning the edit -------------------------------------------------------------------


def test_with_nothing_to_cut_the_whole_film_is_kept() -> None:
    plan = plan_edit([], 100)
    assert plan.keep == [(0.0, 100)]
    assert plan.mute == []
    assert (plan.removed, plan.cuts) == (0, 0)


def test_skipped_scenes_are_taken_out_and_the_rest_is_kept_in_order() -> None:
    plan = plan_edit([cut(60, 70), cut(10, 20)], 100)
    assert plan.keep == [(0.0, 10), (20, 60), (70, 100)]
    assert plan.output_duration == 80
    assert (plan.removed, plan.cuts) == (20, 2)


def test_scenes_that_touch_or_overlap_are_one_cut() -> None:
    plan = plan_edit([cut(10, 20), cut(15, 30), cut(30.1, 40)], 100)
    assert plan.keep == [(0.0, 10), (40, 100)]
    assert plan.cuts == 1


def test_a_scene_at_the_start_or_end_leaves_no_empty_piece() -> None:
    plan = plan_edit([cut(0, 5), cut(95, 100)], 100)
    assert plan.keep == [(5, 95)]
    assert plan.cuts == 2


def test_cuts_past_the_end_of_the_film_are_trimmed() -> None:
    plan = plan_edit([cut(90, 150), cut(-5, 3)], 100)
    assert plan.keep == [(3, 90)]


def test_cutting_everything_leaves_nothing_to_keep() -> None:
    assert plan_edit([cut(0, 100)], 100).keep == []


def test_words_are_muted_a_little_early_and_a_little_late_like_the_player_does() -> None:
    plan = plan_edit([cut(50, 51, FilterAction.MUTE)], 100)
    assert plan.mute == [(50 - MUTE_LEAD_SECONDS, 51 + MUTE_TAIL_SECONDS)]
    assert plan.keep == [(0.0, 100)]  # muting never removes picture


def test_words_inside_a_removed_scene_need_no_mute() -> None:
    plan = plan_edit(
        [cut(10, 40), cut(20, 21, FilterAction.MUTE), cut(60, 61, FilterAction.MUTE)], 100
    )
    assert plan.mute == [(60 - MUTE_LEAD_SECONDS, 61 + MUTE_TAIL_SECONDS)]


def test_neighbouring_mutes_become_one() -> None:
    plan = plan_edit([cut(50, 50.4, FilterAction.MUTE), cut(50.5, 51, FilterAction.MUTE)], 100)
    assert len(plan.mute) == 1


def test_the_fingerprint_follows_the_cuts_and_nothing_else() -> None:
    same = plan_edit([cut(10, 20)], 100)
    assert plan_edit([cut(10, 20)], 100).fingerprint() == same.fingerprint()
    assert plan_edit([cut(10, 21)], 100).fingerprint() != same.fingerprint()
    assert plan_edit([cut(10, 20), cut(5, 6, FilterAction.MUTE)], 100).fingerprint() != (
        same.fingerprint()
    )
    assert plan_edit([cut(10, 20)], 101).fingerprint() != same.fingerprint()


def test_a_copy_made_by_an_older_way_of_rendering_is_out_of_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import velvetdub.domain.export as export

    plan = plan_edit([cut(10, 20)], 100)
    now = plan.fingerprint()
    monkeypatch.setattr(export, "RENDER_VERSION", export.RENDER_VERSION + 1)
    assert plan.fingerprint() != now


# --- the ffmpeg graph --------------------------------------------------------------------


def test_the_graph_keeps_the_same_pieces_of_picture_and_sound() -> None:
    plan = EditPlan(keep=[(0.0, 10.0), (20.0, 100.0)], mute=[(50.0, 51.5)], source_duration=100)
    script = cleaned_filter_script(plan)
    pieces = "between(t,0.000,10.000)+between(t,20.000,100.000)"
    assert f"[0:v]select='{pieces}',setpts=N/FRAME_RATE/TB[v];" in script
    # sound is silenced on the film's own timeline first, then cut to the same pieces
    assert f"[0:a]volume=enable='between(t,50.000,51.500)':volume=0,aselect='{pieces}'" in script
    assert script.rstrip().endswith("asetpts=N/SR/TB[a]")


def test_with_no_cuts_the_graph_does_not_touch_picture_or_sound() -> None:
    script = cleaned_filter_script(EditPlan(keep=[(0.0, 100.0)], mute=[], source_duration=100))
    assert "select" not in script
    assert script == "[0:v]null[v];\n[0:a]anull[a]\n"


def test_nothing_to_keep_is_refused_before_ffmpeg_runs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("shutil.which", lambda name: f"/bin/{name}")
    nothing = EditPlan(keep=[], mute=[], source_duration=100)
    with pytest.raises(ValueError, match="nothing left"):
        FFmpegMediaTool().render_cleaned(tmp_path / "a.mp4", tmp_path / "b.mp4", nothing, print)


# --- a real render (needs ffmpeg) --------------------------------------------------------

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")


def make_clip(path: Path) -> None:
    """20 s: the picture counts seconds in colour bands, and the sound is a steady tone."""
    command = ["ffmpeg", "-y", "-loglevel", "error"]
    command += ["-f", "lavfi", "-i", "testsrc=size=160x90:rate=24:duration=20"]
    command += ["-f", "lavfi", "-i", "sine=frequency=440:duration=20"]
    command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(command, check=True)


def duration_of(path: Path) -> float:
    command = ["ffprobe", "-v", "error", "-show_entries", "format=duration"]
    command += ["-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    out = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return float(out.stdout.strip())


def loudness(path: Path, start: float, length: float) -> float:
    """Mean volume in dB of a stretch of the file (about -20 for the tone, -91 for silence)."""
    command = ["ffmpeg", "-ss", str(start), "-t", str(length), "-i", str(path)]
    command += ["-af", "volumedetect", "-vn", "-f", "null", "-"]
    out = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )
    found = re.search(r"mean_volume: (-?[\d.]+|-inf) dB", out.stderr)
    assert found, out.stderr
    return float("-inf") if found[1] == "-inf" else float(found[1])


@needs_ffmpeg
def test_a_real_copy_loses_the_cut_scene_and_silences_the_word(tmp_path: Path) -> None:
    source, dest = tmp_path / "in.mp4", tmp_path / "out" / "cleaned.mp4"
    make_clip(source)
    plan = plan_edit([cut(4, 8), cut(12, 13, FilterAction.MUTE)], 20)
    progress: list[float] = []

    FFmpegMediaTool().render_cleaned(source, dest, plan, progress.append)

    assert dest.is_file()
    assert not list(dest.parent.glob("*.partial*")) and not list(dest.parent.glob("*.txt"))
    assert duration_of(dest) == pytest.approx(16.0, abs=0.3)  # 20 s less the 4 s scene
    assert progress[-1] == 1.0 and progress == sorted(progress)
    # the word was at 12-13 s of the film, which is 8-9 s into the copy (plus its safety margin)
    assert loudness(dest, 8.1, 0.6) < -60
    assert loudness(dest, 1, 2) > -35  # ordinary sound before the scene is untouched
    assert loudness(dest, 12, 3) > -35  # and after the word


# --- the job and the API -----------------------------------------------------------------


@pytest.fixture
def processed(container: Container, source_file: Path) -> Manifest:
    manifest = container.store.create("local", "Wolf: of/Wall Street", source_file)
    container.process(
        manifest, ProcessOptions(filter_categories=[*PICTURE_CATEGORIES, FilterCategory.SWEARING])
    )
    return manifest


@pytest.fixture
def client(container: Container) -> TestClient:
    return TestClient(create_app(container), headers=CLIENT)


def url(manifest: Manifest) -> str:
    return f"/api/titles/{manifest.title_id}/export"


def wait_for(client: TestClient, manifest: Manifest, status: str) -> dict[str, object]:
    for _ in range(200):
        state = client.get(url(manifest)).json()
        if state["status"] == status:
            return state  # type: ignore[no-any-return]
        time.sleep(0.02)
    raise AssertionError(f"never became {status}: {state}")


def test_the_state_says_what_the_copy_would_be_like_before_anything_is_made(
    client: TestClient, processed: Manifest
) -> None:
    state = client.get(url(processed)).json()
    assert state["status"] == "none"
    # the fake scan's violence at 10-20 s, widened by a second each side, plus the muted "hell"
    assert state["removed_seconds"] == 12.0
    assert state["output_seconds"] == 48.0
    assert (state["cuts"], state["muted_words"]) == (1, 1)
    assert state["filename"] == "Wolf of Wall Street (cleaned).mp4"


def test_making_the_copy_runs_in_the_background_then_it_can_be_downloaded(
    client: TestClient, processed: Manifest, media: FakeMediaTool
) -> None:
    assert client.get(f"{url(processed)}/file").status_code == 409  # nothing to download yet

    started = client.post(url(processed))
    assert started.status_code == 202
    ready = wait_for(client, processed, "ready")
    assert ready["percent"] == 100
    assert ready["size_bytes"] == len(b"cleaned-video")

    (plan,) = media.render_calls
    assert plan.keep == [(0.0, 9.0), (21.0, 60.0)]
    assert len(plan.mute) == 1

    download = client.get(f"{url(processed)}/file")
    assert download.status_code == 200
    assert download.content == b"cleaned-video"
    assert download.headers["content-type"] == "video/mp4"
    disposition = unquote(download.headers["content-disposition"])
    assert disposition.startswith("attachment;")
    assert "Wolf of Wall Street (cleaned).mp4" in disposition


def test_asking_again_with_nothing_changed_reuses_the_saved_copy(
    client: TestClient, processed: Manifest, media: FakeMediaTool
) -> None:
    client.post(url(processed))
    wait_for(client, processed, "ready")

    again = client.post(url(processed)).json()
    assert again["status"] == "ready"
    assert len(media.render_calls) == 1


def test_changing_a_cut_makes_the_saved_copy_out_of_date_and_remakes_it(
    client: TestClient, processed: Manifest, media: FakeMediaTool
) -> None:
    client.post(url(processed))
    wait_for(client, processed, "ready")

    scene = next(
        f
        for f in client.get("/api/titles/" + processed.title_id + "/playback").json()["filters"]
        if f["action"] == "skip"
    )
    client.put(f"/api/titles/{processed.title_id}/events/{scene['id']}/keep")

    assert client.get(url(processed)).json()["status"] == "none"
    assert client.get(f"{url(processed)}/file").status_code == 409  # the old copy is not offered

    client.post(url(processed))
    wait_for(client, processed, "ready")
    assert len(media.render_calls) == 2
    assert media.render_calls[1].keep == [(0.0, 60.0)]  # the scene was left in


def test_a_failed_render_says_why_and_can_be_tried_again(
    client: TestClient, container: Container, processed: Manifest
) -> None:
    class Broken(FakeMediaTool):
        def render_cleaned(self, source, dest, plan, on_progress):  # type: ignore[no-untyped-def]
            raise subprocess.CalledProcessError(1, "ffmpeg", stderr="line one\nNo such encoder\n")

    container.exports._media = Broken()
    client.post(url(processed))
    failed = wait_for(client, processed, "failed")
    assert failed["error"] == "The copy could not be made: No such encoder"

    container.exports._media = FakeMediaTool()
    client.post(url(processed))
    wait_for(client, processed, "ready")


def test_other_users_cannot_see_or_make_a_copy(container: Container, processed: Manifest) -> None:
    from starlette.requests import Request

    from velvetdub.auth.identity import IdentityProvider
    from velvetdub.domain.user import User

    class Someone(IdentityProvider):
        def current_user(self, request: Request) -> User:
            return User(id="intruder", display_name="x")

    container.identity = Someone()
    other = TestClient(create_app(container), headers=CLIENT)
    assert other.get(url(processed)).status_code == 404
    assert other.post(url(processed)).status_code == 404
    assert other.get(f"{url(processed)}/file").status_code == 404


def test_the_status_is_an_enum_the_page_can_rely_on() -> None:
    assert {s.value for s in ExportStatus} == {"none", "working", "ready", "failed"}


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Harbor Lights 1947", "Harbor Lights 1947 (cleaned).mp4"),
        ('A/B: "C"?', "A B C (cleaned).mp4"),
        ("   ", "film (cleaned).mp4"),
        ("..", "film (cleaned).mp4"),
    ],
)
def test_download_names_are_safe_to_save(title: str, expected: str) -> None:
    assert download_name(title) == expected
