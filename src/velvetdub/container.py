"""Composition root: the one place that decides which concrete classes the app uses.

The CLI and the API both build a Container. Tests build one with fakes. Swapping storage,
identity or media tooling means changing the wiring here and nowhere else.
"""

from dataclasses import dataclass

from velvetdub.auth.identity import IdentityProvider, LocalIdentityProvider
from velvetdub.config.settings import Settings
from velvetdub.domain.filtering import FilterPolicy
from velvetdub.domain.manifest import Choices, Manifest
from velvetdub.features.scene_filtering.categories import in_scan_order
from velvetdub.media.tools import FFmpegMediaTool, MediaTool
from velvetdub.pipeline.context import PipelineContext, ProcessOptions
from velvetdub.pipeline.observer import NullObserver, PipelineObserver
from velvetdub.pipeline.runner import PipelineRunner
from velvetdub.pipeline.stages import phase1_stages
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
            filter_categories=in_scan_order(options.filter_categories),
            subtitle_languages=list(options.subtitle_languages),
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
        PipelineRunner(phase1_stages(), self.store).run(ctx)


def build_container(
    settings: Settings | None = None, *, media: MediaTool | None = None
) -> Container:
    settings = settings or Settings()
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
        jobs=JobManager(run, [stage.name for stage in phase1_stages()]),
    )
    return container
