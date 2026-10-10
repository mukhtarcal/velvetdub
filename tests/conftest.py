from pathlib import Path

import pytest

from velvetdub.config.settings import Settings
from velvetdub.container import Container, build_container
from velvetdub.media.tools import MediaTool, ScanClip


class FakeMediaTool(MediaTool):
    def __init__(self) -> None:
        self.extract_calls = 0

    def extract_audio(self, source: Path, dest: Path) -> None:
        self.extract_calls += 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-audio")

    def probe_duration(self, source: Path) -> float:
        return 60.0

    def make_scan_clips(
        self, source: Path, out_dir: Path, *, clip_seconds: int, fps: float, height: int
    ) -> list[ScanClip]:
        out_dir.mkdir(parents=True, exist_ok=True)
        clip = out_dir / "clip_0000.mp4"
        clip.write_bytes(b"fake-clip")
        return [ScanClip(path=clip, offset=0.0, duration=60.0)]


@pytest.fixture
def media() -> FakeMediaTool:
    return FakeMediaTool()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # _env_file=None so a developer's real .env can never leak into tests
    return Settings(
        _env_file=None,
        data_dir=tmp_path / "data",
        allowed_hosts=["testserver"],
        transcription_provider="fake",
        translation_provider="fake",
        moderation_provider="fake",
    )


@pytest.fixture
def container(settings: Settings, media: FakeMediaTool) -> Container:
    return build_container(settings, media=media)


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "movie.mp4"
    path.write_bytes(b"fake-video")
    return path
