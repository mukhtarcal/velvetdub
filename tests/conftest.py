from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from velvetdub.config.settings import Settings
from velvetdub.container import Container, build_container
from velvetdub.domain.dubbing import Ambience, Placement
from velvetdub.domain.export import EditPlan, Span
from velvetdub.media.dialogue import wav_seconds
from velvetdub.media.tools import MediaTool, ScanClip
from velvetdub.providers.fake import write_tone


class FakeMediaTool(MediaTool):
    def __init__(self) -> None:
        self.extract_calls = 0
        self.poster_calls: list[float] = []
        self.render_calls: list[EditPlan] = []
        self.cut_calls: list[list[Span]] = []
        self.tempo_calls: list[float] = []
        self.mix_calls: list[list[Placement]] = []
        self.mix_options: list[tuple[Ambience | None, float | None]] = []
        self.levels: list[float] = []  # what level_profile reports, one reading a second
        self.film_loudness: float | None = -24.0
        self.level_calls = 0
        self.level_steps: list[float] = []
        self.fine_levels: list[float] = []  # what level_profile reports for a step under a second

    def extract_audio(self, source: Path, dest: Path) -> None:
        self.extract_calls += 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-audio")

    def probe_duration(self, source: Path) -> float:
        return 60.0

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
        clip = out_dir / "clip_0000.mp4"
        clip.write_bytes(b"fake-clip")
        return [ScanClip(path=clip, offset=0.0, duration=60.0)]

    def extract_frames(self, clip: Path, out_dir: Path) -> list[Path]:
        out_dir.mkdir(parents=True, exist_ok=True)
        frames = [out_dir / f"f_{n:05d}.jpg" for n in range(1, 31)]
        for frame in frames:
            frame.write_bytes(b"frame")
        return frames

    def render_cleaned(
        self, source: Path, dest: Path, plan: EditPlan, on_progress: Callable[[float], None]
    ) -> None:
        self.render_calls.append(plan)
        on_progress(0.5)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"cleaned-video")
        on_progress(1.0)

    def extract_poster(self, source: Path, dest: Path, *, at_seconds: float) -> None:
        self.poster_calls.append(at_seconds)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"jpeg")

    def extract_mix(self, source: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-mix")

    def cut_audio(self, source: Path, spans: Sequence[Span], dest: Path) -> None:
        self.cut_calls.append(list(spans))
        write_tone(dest, sum(end - start for start, end in spans))

    def change_tempo(self, source: Path, dest: Path, factor: float) -> None:
        self.tempo_calls.append(factor)
        write_tone(dest, wav_seconds(source) / factor)

    def level_profile(self, source: Path, step: float = 1.0) -> list[float]:
        self.level_calls += 1
        self.level_steps.append(step)
        return list(self.levels) if step >= 1.0 else list(self.fine_levels)

    def measure_loudness(self, source: Path) -> float | None:
        return self.film_loudness

    def mix_dub(
        self,
        lines: Sequence[Placement],
        background: Path,
        dest: Path,
        *,
        ambience: Ambience | None = None,
        loudness: float | None = None,
    ) -> None:
        self.mix_calls.append(list(lines))
        self.mix_options.append((ambience, loudness))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake-dub")


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
        tts_provider="fake",
        separation_provider="fake",
    )


@pytest.fixture
def container(settings: Settings, media: FakeMediaTool) -> Container:
    return build_container(settings, media=media)


@pytest.fixture
def source_file(tmp_path: Path) -> Path:
    path = tmp_path / "movie.mp4"
    path.write_bytes(b"fake-video")
    return path
