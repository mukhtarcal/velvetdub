"""Command line: `uv run vd --help`."""

import shutil
from pathlib import Path
from typing import Annotated

import typer

from velvetdub.config.settings import Settings
from velvetdub.container import build_container
from velvetdub.domain.user import LOCAL_USER
from velvetdub.errors import StageFailedError, VelvetDubError
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

    def report(label: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and passed
        mark = (
            typer.style("ok  ", fg=typer.colors.GREEN)
            if passed
            else typer.style("MISS", fg=typer.colors.RED)
        )
        typer.echo(f"[{mark}] {label}{(' - ' + detail) if detail else ''}")

    for binary in ("ffmpeg", "ffprobe"):
        report(binary, shutil.which(binary) is not None)

    providers = ProviderSet(settings)
    checks = {
        "transcription": ("transcriber", settings.transcription_provider),
        "translation": ("translator", settings.translation_provider),
        "visual moderation": ("moderator", settings.moderation_provider),
        "text moderation": ("text_moderator", settings.text_moderation_provider),
    }
    for label, (attr, name) in checks.items():
        try:
            provider = getattr(providers, attr)
            report(f"{label}: {name}", True, provider.identity)
        except VelvetDubError as exc:
            report(f"{label}: {name}", False, str(exc))

    typer.echo(f"data dir: {settings.data_path}")
    raise typer.Exit(code=0 if ok else 1)


@app.command()
def providers() -> None:
    """List the registered providers for each capability."""
    for reg in (
        registry.transcribers,
        registry.translators,
        registry.moderators,
        registry.text_moderators,
        registry.separators,
        registry.synthesizers,
    ):
        typer.echo(f"{reg.kind}: {', '.join(reg.names()) or '(none yet)'}")


@app.command()
def process(
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
    subs: Annotated[str, typer.Option(help="Comma-separated subtitle languages")] = "en",
    name: Annotated[str | None, typer.Option(help="Title name (default: file name)")] = None,
    title_id: Annotated[str | None, typer.Option(help="Re-run an existing title")] = None,
) -> None:
    """Add a film and run the pipeline (re-running skips finished stages)."""
    languages = [lang.strip() for lang in subs.split(",") if lang.strip()]
    if not languages:
        typer.secho("--subs needs at least one language code", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        container = build_container()
        # The CLI is single-user by nature; the API resolves the user per request instead.
        if title_id is None:
            manifest = container.store.create(LOCAL_USER.id, name or file.stem, file)
        else:
            manifest = container.store.get(LOCAL_USER.id, title_id)
        typer.echo(f"Title {manifest.title_id}: {manifest.name}")
        container.process(manifest, ProcessOptions(subtitle_languages=languages), ConsoleObserver())
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
def serve(port: int = 8765) -> None:
    """Run the API on localhost only."""
    import uvicorn

    uvicorn.run("velvetdub.api.app:create_app", factory=True, host="127.0.0.1", port=port)
