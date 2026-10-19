"""Command line: `uv run vd --help`."""

import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from velvetdub.config.settings import Settings
from velvetdub.container import build_container
from velvetdub.domain.filtering import FilterCategory
from velvetdub.domain.user import LOCAL_USER
from velvetdub.errors import StageFailedError, VelvetDubError
from velvetdub.features.dubbing.support import dubbing_languages
from velvetdub.features.scene_filtering.categories import PICTURE_CATEGORIES
from velvetdub.features.scene_filtering.factory import build_scene_scanner, scannable_categories
from velvetdub.pipeline.context import ProcessOptions
from velvetdub.pipeline.observer import PipelineObserver
from velvetdub.providers import registry
from velvetdub.providers.provider_set import ProviderSet

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Velvet Dub")


class ConsoleObserver(PipelineObserver):
    def stage_started(self, stage: str) -> None:
        typer.echo(f"  ...  {stage}")

    def stage_skipped(self, stage: str) -> None:
        typer.echo(f"  skip {stage} (up to date)")

    def stage_finished(self, stage: str) -> None:
        typer.echo(f"  done {stage}")

    def stage_failed(self, stage: str, error: str) -> None:
        typer.secho(f"  FAIL {stage}: {error}", fg=typer.colors.RED)


@app.command()
def doctor() -> None:
    """Check that tools, keys and chosen providers are ready (never prints key values)."""
    settings = Settings()
    ok = True

    def report(label: str, passed: bool, detail: str = "", *, optional: bool = False) -> None:
        nonlocal ok
        ok = ok and (passed or optional)
        if passed:
            mark = typer.style("ok  ", fg=typer.colors.GREEN)
        elif optional:
            mark = typer.style("skip", fg=typer.colors.YELLOW)
        else:
            mark = typer.style("MISS", fg=typer.colors.RED)
        typer.echo(f"[{mark}] {label}{(' - ' + detail) if detail else ''}")

    for binary in ("ffmpeg", "ffprobe"):
        report(binary, shutil.which(binary) is not None)

    providers = ProviderSet(settings)
    checks: dict[str, tuple[Callable[[], Any], str]] = {
        "transcription": (lambda: providers.transcriber, settings.transcription_provider),
        "translation": (lambda: providers.text_generator, settings.translation_provider),
        "visual moderation": (
            lambda: build_scene_scanner(providers, settings, []),
            settings.moderation_provider,
        ),
        "text moderation": (lambda: providers.text_moderator, settings.text_moderation_provider),
    }
    for label, (get, name) in checks.items():
        try:
            provider = get()
            report(f"{label}: {name}", True, provider.identity)
        except VelvetDubError as exc:
            report(f"{label}: {name}", False, str(exc))

    # Dubbing is optional: not being set up is reported, but does not fail the check.
    dubbing: dict[str, tuple[Callable[[], Any], str]] = {
        "dubbing, voice separation": (lambda: providers.separator, settings.separation_provider),
        "dubbing, speech": (lambda: providers.synthesizer, settings.tts_provider),
    }
    for label, (get, name) in dubbing.items():
        try:
            report(f"{label}: {name}", True, get().identity, optional=True)
        except VelvetDubError as exc:
            report(f"{label}: {name}", False, str(exc), optional=True)

    typer.echo(f"data dir: {settings.data_path}")
    raise typer.Exit(code=0 if ok else 1)


@app.command()
def providers() -> None:
    """List the registered providers for each capability."""
    for reg in (
        registry.transcribers,
        registry.text_generators,
        registry.video_analyzers,
        registry.frame_judges,
        registry.text_moderators,
        registry.separators,
        registry.synthesizers,
    ):
        typer.echo(f"{reg.kind}: {', '.join(reg.names()) or '(none yet)'}")


@app.command()
def process(
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    subs: Annotated[
        str, typer.Option(help="Comma-separated subtitle languages (default: none)")
    ] = "",
    dub: Annotated[
        str,
        typer.Option(
            help="Comma-separated languages to dub into, in copies of each speaker's voice "
            "(default: none; needs `uv sync --group dubbing` and CARTESIA_API_KEY)"
        ),
    ] = "",
    filters: Annotated[
        str,
        typer.Option(
            help="Comma-separated filters to run: nudity, sexual_content, scary_scenes, "
            "violence (scanned in the picture) and swearing (found from the dialogue). "
            "Only what is chosen is processed (default: none)"
        ),
    ] = "",
    name: Annotated[str | None, typer.Option(help="Title name (default: file name)")] = None,
    title_id: Annotated[str | None, typer.Option(help="Re-run an existing title")] = None,
) -> None:
    """Add a film and run the pipeline (re-running skips finished stages)."""
    languages = [lang.strip() for lang in subs.split(",") if lang.strip()]
    dub_languages = [lang.strip() for lang in dub.split(",") if lang.strip()]
    try:
        categories = [FilterCategory(c.strip()) for c in filters.split(",") if c.strip()]
    except ValueError as exc:
        typer.secho(f"--filters: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    offered = (*PICTURE_CATEGORIES, FilterCategory.SWEARING)
    not_offered = [c for c in categories if c not in offered]
    if not_offered:
        typer.secho(f"--filters: {not_offered[0].value} can't be chosen", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        container = build_container()
        scanned = [c for c in categories if c in PICTURE_CATEGORIES]
        unsupported = [c for c in scanned if c not in scannable_categories(container.settings)]
        if unsupported:
            typer.secho(
                f"This scanner can't check for {unsupported[0].value.replace('_', ' ')}.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)
        if dub_languages:
            available = dubbing_languages(container.providers)
            if not available:
                typer.secho(
                    "Dubbing isn't set up: add CARTESIA_API_KEY to .env and run "
                    "`uv sync --group dubbing`.",
                    fg=typer.colors.RED,
                )
                raise typer.Exit(code=1)
            missing = [lang for lang in dub_languages if lang not in available]
            if missing:
                typer.secho(f"Dubbing can't speak: {', '.join(missing)}", fg=typer.colors.RED)
                raise typer.Exit(code=1)
        # The CLI is single-user by nature; the API resolves the user per request instead.
        if title_id is None:
            manifest = container.store.create(LOCAL_USER.id, name or file.stem, file)
        else:
            manifest = container.store.get(LOCAL_USER.id, title_id)
        typer.echo(f"Title {manifest.title_id}: {manifest.name}")
        container.process(
            manifest,
            ProcessOptions(
                subtitle_languages=languages,
                filter_categories=categories,
                dub_languages=dub_languages,
            ),
            ConsoleObserver(),
        )
    except StageFailedError as exc:
        typer.secho(f"{exc} ({exc.__cause__})", fg=typer.colors.RED)
        typer.echo(f"Fix the problem, then re-run with --title-id {manifest.title_id}")
        raise typer.Exit(code=1) from exc
    except VelvetDubError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Finished. Files are in {container.store.paths(manifest).root}")


@app.command()
def titles() -> None:
    """List your titles."""
    container = build_container()
    for manifest in container.store.list(LOCAL_USER.id):
        done = sum(1 for r in manifest.stages.values() if r.status.value == "done")
        typer.echo(f"{manifest.title_id}  {manifest.name}  ({done} stages done)")


@app.command()
def serve(
    port: int = 8765,
    reload: Annotated[
        bool, typer.Option(help="Restart when the code changes (for development)")
    ] = False,
) -> None:
    """Run the API on localhost only."""
    import uvicorn

    uvicorn.run(
        "velvetdub.api.app:create_app",
        factory=True,
        host="127.0.0.1",
        port=port,
        reload=reload,
        reload_dirs=["src"] if reload else None,
    )
