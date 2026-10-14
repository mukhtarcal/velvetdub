import subprocess
from pathlib import Path

import pytest

from velvetdub.media.tools import FFmpegMediaTool


def test_the_poster_is_one_typical_frame_from_near_the_given_time(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("shutil.which", lambda name: f"/bin/{name}")
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", lambda command, **_: calls.append(command))

    FFmpegMediaTool().extract_poster(
        tmp_path / "film.mp4", tmp_path / "out" / "poster.jpg", at_seconds=648.5
    )

    (command,) = calls
    assert command[command.index("-ss") + 1] == "648.50"
    assert command.index("-ss") < command.index("-i")  # seek before reading: fast on long films
    assert "thumbnail=100,scale=640:-2" in command
    assert command[command.index("-frames:v") + 1] == "1"
    assert command[-1].endswith("poster.jpg")
    assert (tmp_path / "out").is_dir()
