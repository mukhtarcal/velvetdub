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
        return self.keep_many(owner_id, title_id, [event_id], keep=keep)

    def keep_many(
        self, owner_id: str, title_id: str, event_ids: list[str], *, keep: bool
    ) -> Overrides:
        """Keep in (or filter again) several detections at once, such as every mild word."""
        current = self.get(owner_id, title_id)
        changing = set(event_ids)
        ids = [i for i in current.keep if i not in changing]
        if keep:
            ids.extend(dict.fromkeys(event_ids))
        updated = Overrides(keep=ids)
        manifest = self._store.get(owner_id, title_id)
        write_model(self._store.paths(manifest).overrides, updated)
        return updated
