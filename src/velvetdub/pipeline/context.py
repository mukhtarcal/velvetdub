"""Everything a stage may use, passed in explicitly (no globals)."""

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from velvetdub.config.settings import Settings
from velvetdub.domain.manifest import Manifest
from velvetdub.media.tools import MediaTool
from velvetdub.pipeline.observer import NullObserver, PipelineObserver
from velvetdub.providers.provider_set import ProviderSet
from velvetdub.storage.paths import TitlePaths


class ProcessOptions(BaseModel):
    """What the user asked for. `dub_languages` is used from Phase 2."""

    subtitle_languages: list[str] = Field(default_factory=lambda: ["en"])
    dub_languages: list[str] = Field(default_factory=list)
    source_language: str | None = None  # None = auto-detect

    @property
    def target_languages(self) -> list[str]:
        """Every language needing a translation, without duplicates, in order."""
        return list(dict.fromkeys([*self.subtitle_languages, *self.dub_languages]))


@dataclass
class PipelineContext:
    manifest: Manifest
    paths: TitlePaths
    settings: Settings
    providers: ProviderSet
    media: MediaTool
    options: ProcessOptions = field(default_factory=ProcessOptions)
    observer: PipelineObserver = field(default_factory=NullObserver)
