"""Everything a stage may use, passed in explicitly (no globals)."""

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from velvetdub.config.settings import Settings
from velvetdub.domain.filtering import FilterCategory
from velvetdub.domain.manifest import Manifest
from velvetdub.features.scene_filtering.categories import in_scan_order
from velvetdub.media.tools import MediaTool
from velvetdub.pipeline.observer import NullObserver, PipelineObserver
from velvetdub.providers.provider_set import ProviderSet
from velvetdub.storage.paths import TitlePaths


class ProcessOptions(BaseModel):
    """What the user asked for. Only that is run: with nothing chosen, nothing is processed.

    Every list defaults to empty: no filters, no subtitles, no dub. `filter_categories` holds the
    four picture categories and swearing. Subtitles and dubs are translated separately (a dub is
    written to be spoken, and from a cleaner transcript), so a language in both is translated
    twice on purpose."""

    subtitle_languages: list[str] = Field(default_factory=list)
    filter_categories: list[FilterCategory] = Field(default_factory=list)
    dub_languages: list[str] = Field(default_factory=list)
    source_language: str | None = None  # None = auto-detect

    @property
    def picture_categories(self) -> list[FilterCategory]:
        """What the picture scan looks for. Empty means the scan (and Gemini) is not used."""
        return in_scan_order(self.filter_categories)

    @property
    def finds_swearing(self) -> bool:
        return FilterCategory.SWEARING in self.filter_categories

    @property
    def needs_transcript(self) -> bool:
        """The film's own dialogue is transcribed only for swearing or subtitles. A dub listens to
        the separated dialogue instead, so a dub alone does not need it."""
        return self.finds_swearing or bool(self.subtitle_languages)


@dataclass
class PipelineContext:
    manifest: Manifest
    paths: TitlePaths
    settings: Settings
    providers: ProviderSet
    media: MediaTool
    options: ProcessOptions = field(default_factory=ProcessOptions)
    observer: PipelineObserver = field(default_factory=NullObserver)
