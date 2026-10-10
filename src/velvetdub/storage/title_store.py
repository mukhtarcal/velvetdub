"""Title storage.

`TitleStore` is the interface the rest of the app uses. Every call takes an `owner_id`, so a
multi-user version only needs a store that enforces it (the filesystem one already does).
A cloud version (object storage + a database) would be another subclass.
"""

import shutil
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from velvetdub.domain.manifest import Manifest
from velvetdub.errors import TitleNotFoundError
from velvetdub.storage.artifacts import read_model, write_model
from velvetdub.storage.paths import TitlePaths


class TitleStore(ABC):
    @abstractmethod
    def create(self, owner_id: str, name: str, source: Path, *, move: bool = False) -> Manifest:
        """Register a title and bring its source file in.

        By default the file is copied and the original is untouched. `move=True` is for files
        the app itself just wrote (uploads), to avoid copying a multi-gigabyte film twice."""

    @abstractmethod
    def get(self, owner_id: str, title_id: str) -> Manifest: ...

    @abstractmethod
    def list(self, owner_id: str) -> list[Manifest]: ...

    @abstractmethod
    def save(self, manifest: Manifest) -> None: ...

    @abstractmethod
    def paths(self, manifest: Manifest) -> TitlePaths: ...


class FileSystemTitleStore(TitleStore):
    def __init__(self, data_dir: Path) -> None:
        self._titles_dir = data_dir / "titles"

    def create(self, owner_id: str, name: str, source: Path, *, move: bool = False) -> Manifest:
        if not source.is_file():
            raise FileNotFoundError(source)
        title_id = uuid.uuid4().hex[:12]
        manifest = Manifest(
            title_id=title_id,
            owner_id=owner_id,
            name=name,
            source_filename=f"source{source.suffix}",
        )
        paths = self.paths(manifest)
        paths.root.mkdir(parents=True)
        if move:
            shutil.move(source, paths.source)
        else:
            shutil.copy2(source, paths.source)
        self.save(manifest)
        return manifest

    def get(self, owner_id: str, title_id: str) -> Manifest:
        manifest_path = self._titles_dir / title_id / "manifest.json"
        if not manifest_path.is_file():
            raise TitleNotFoundError(title_id)
        manifest = read_model(manifest_path, Manifest)
        if manifest.owner_id != owner_id:
            raise TitleNotFoundError(title_id)  # never reveal that another user's title exists
        return manifest

    def list(self, owner_id: str) -> list[Manifest]:
        if not self._titles_dir.is_dir():
            return []
        manifests = [
            read_model(path, Manifest) for path in sorted(self._titles_dir.glob("*/manifest.json"))
        ]
        return sorted(
            (m for m in manifests if m.owner_id == owner_id),
            key=lambda m: m.created_at,
            reverse=True,
        )

    def save(self, manifest: Manifest) -> None:
        write_model(self.paths(manifest).manifest, manifest)

    def paths(self, manifest: Manifest) -> TitlePaths:
        return TitlePaths(self._titles_dir / manifest.title_id, manifest.source_filename)
