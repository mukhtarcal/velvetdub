from velvetdub.domain.overrides import Overrides
from velvetdub.storage.artifacts import read_model, write_model
from velvetdub.storage.title_store import TitleStore


class OverrideService:
    """Remembers which detections the viewer chose to keep in, per title."""

    def __init__(self, store: TitleStore) -> None:
        self._store = store

    def get(self, owner_id: str, title_id: str) -> Overrides:
        manifest = self._store.get(owner_id, title_id)
        path = self._store.paths(manifest).overrides
        return read_model(path, Overrides) if path.exists() else Overrides()

    def keep(self, owner_id: str, title_id: str, event_id: str, *, keep: bool) -> Overrides:
        current = self.get(owner_id, title_id)
        ids = [i for i in current.keep if i != event_id]
        if keep:
            ids.append(event_id)
        updated = Overrides(keep=ids)
        manifest = self._store.get(owner_id, title_id)
        write_model(self._store.paths(manifest).overrides, updated)
        return updated
