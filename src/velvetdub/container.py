"""Composition root: the one place that decides which concrete classes the app uses.

The CLI and the API both build a Container. Tests build one with fakes. Swapping storage,
identity or media tooling means changing the wiring here and nowhere else.
"""

import os
from dataclasses import dataclass

from velvetdub.auth.identity import IdentityProvider, LocalIdentityProvider
from velvetdub.config.settings import Settings
from velvetdub.domain.filtering import FilterPolicy
from velvetdub.domain.manifest import Choices, Manifest
from velvetdub.features.scene_filtering.categories import in_choice_order
from velvetdub.media.tools import FFmpegMediaTool, MediaTool
from velvetdub.pipeline.context import PipelineContext, ProcessOptions
from velvetdub.pipeline.observer import NullObserver, PipelineObserver
from velvetdub.pipeline.runner import PipelineRunner
from velvetdub.pipeline.stages import all_stages
from velvetdub.providers.provider_set import ProviderSet
from velvetdub.services.exports import ExportService
from velvetdub.services.jobs import JobManager
from velvetdub.services.overrides import OverrideService
from velvetdub.services.playback import PlaybackService
from velvetdub.services.posters import PosterService
from velvetdub.services.subtitles import SubtitleService
from velvetdub.storage.corrections import CorrectionRepository, SqliteCorrectionRepository
from velvetdub.storage.title_store import FileSystemTitleStore, TitleStore


@dataclass
class Container:
    settings: Settings
    store: TitleStore
    identity: IdentityProvider
    providers: ProviderSet
    media: MediaTool
    policy: FilterPolicy
    corrections: CorrectionRepository
    overrides: OverrideService
    playback: PlaybackService
    posters: PosterService
    exports: ExportService
    subtitles: SubtitleService
    jobs: JobManager

    def process(
        self,
        manifest: Manifest,
        options: ProcessOptions,
        observer: PipelineObserver | None = None,
    ) -> None:
        manifest.choices = Choices(
            filter_categories=in_choice_order(options.filter_categories),
            subtitle_languages=list(options.subtitle_languages),
            dub_languages=list(options.dub_languages),
        )
        self.store.save(manifest)
        ctx = PipelineContext(
            manifest=manifest,
            paths=self.store.paths(manifest),
            settings=self.settings,
            providers=self.providers,
            media=self.media,
            options=options,
            observer=observer or NullObserver(),
        )
        PipelineRunner(all_stages(), self.store).run(ctx)


def keep_model_downloads_in_project(settings: Settings) -> None:
    """Model weights (Demucs) download into `data/cache/`, not `~/.cache`. Must run before the
    libraries that read these variables are first imported, which is why it is done here."""
    if settings.separation_provider == "demucs":
        cache = settings.model_cache_path
        os.environ["HF_HOME"] = str(cache / "huggingface")
        os.environ["TORCH_HOME"] = str(cache / "torch")


def build_container(
    settings: Settings | None = None, *, media: MediaTool | None = None
) -> Container:
    settings = settings or Settings()
    keep_model_downloads_in_project(settings)
    store = FileSystemTitleStore(settings.data_path)
    policy = FilterPolicy()
    overrides = OverrideService(store)
    playback = PlaybackService(store, overrides, policy)

    def run(manifest: Manifest, options: ProcessOptions, observer: PipelineObserver) -> None:
        container.process(manifest, options, observer)

    media_tool = media or FFmpegMediaTool()
    container = Container(
        settings=settings,
        store=store,
        identity=LocalIdentityProvider(),
        providers=ProviderSet(settings),
        media=media_tool,
        policy=policy,
        corrections=SqliteCorrectionRepository(settings.data_path / "velvetdub.db"),
        overrides=overrides,
        playback=playback,
        posters=PosterService(store, media_tool),
        exports=ExportService(store, playback, media_tool),
        subtitles=SubtitleService(store, playback),
        jobs=JobManager(run, [stage.name for stage in all_stages()]),
    )
    return container
