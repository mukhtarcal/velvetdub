from pathlib import Path

import pytest

from velvetdub.errors import TitleNotFoundError
from velvetdub.storage.title_store import FileSystemTitleStore


def test_create_copies_source_and_leaves_original(tmp_path: Path, source_file: Path) -> None:
    store = FileSystemTitleStore(tmp_path / "data")
    manifest = store.create("alice", "My Movie", source_file)

    assert store.paths(manifest).source.read_bytes() == b"fake-video"
    assert source_file.exists()


def test_titles_are_private_to_their_owner(tmp_path: Path, source_file: Path) -> None:
    store = FileSystemTitleStore(tmp_path / "data")
    manifest = store.create("alice", "Alice's", source_file)

    assert [m.title_id for m in store.list("alice")] == [manifest.title_id]
    assert store.list("bob") == []
    with pytest.raises(TitleNotFoundError):
        store.get("bob", manifest.title_id)


def test_manifest_round_trips(tmp_path: Path, source_file: Path) -> None:
    store = FileSystemTitleStore(tmp_path / "data")
    manifest = store.create("alice", "Movie", source_file)
    assert store.get("alice", manifest.title_id) == manifest


def test_missing_source_file(tmp_path: Path) -> None:
    store = FileSystemTitleStore(tmp_path / "data")
    with pytest.raises(FileNotFoundError):
        store.create("alice", "x", tmp_path / "nope.mp4")
