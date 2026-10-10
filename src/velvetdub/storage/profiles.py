"""Where filter profiles come from.

`ProfileRepository` is the interface. Today profiles are the built-in presets; step 1.4 adds a
database-backed repository (custom profiles per household member, PIN-locked parent) behind the
same interface.
"""

from abc import ABC, abstractmethod

from velvetdub.domain.filtering import FilterProfile
from velvetdub.domain.presets import PRESETS, profile_from_preset
from velvetdub.errors import VelvetDubError

DEFAULT_PROFILE_ID = "family"

PRESET_NAMES = {
    "kids": "Kids (G)",
    "family": "Family (PG)",
    "teen": "Teen",
    "language_only": "Language only",
}


class ProfileNotFoundError(VelvetDubError):
    """No profile with that id."""


class ProfileRepository(ABC):
    @abstractmethod
    def list(self, owner_id: str) -> list[FilterProfile]: ...

    @abstractmethod
    def get(self, owner_id: str, profile_id: str) -> FilterProfile: ...


class PresetProfileRepository(ProfileRepository):
    def list(self, owner_id: str) -> list[FilterProfile]:
        return [
            profile_from_preset(
                preset, profile_id=preset, owner_id=owner_id, name=PRESET_NAMES.get(preset, preset)
            )
            for preset in PRESETS
        ]

    def get(self, owner_id: str, profile_id: str) -> FilterProfile:
        for profile in self.list(owner_id):
            if profile.id == profile_id:
                return profile
        raise ProfileNotFoundError(profile_id)
