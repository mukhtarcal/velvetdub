from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from velvetdub import __version__
from velvetdub.api.guard import LocalOnlyGuard
from velvetdub.api.routers import exports, health, media, playback, subtitles, titles
from velvetdub.container import Container, build_container
from velvetdub.errors import (
    InvalidNameError,
    ProviderError,
    TitleNotFoundError,
    VelvetDubError,
)
from velvetdub.services.subtitles import SubtitleNotFoundError
from velvetdub.subtitles.formats import SubtitleParseError

# Domain errors -> HTTP status. Anything not listed is a genuine bug and stays a 500.
STATUS_FOR_ERROR: dict[type[VelvetDubError], int] = {
    TitleNotFoundError: 404,
    SubtitleNotFoundError: 404,
    InvalidNameError: 422,
    SubtitleParseError: 422,
    ProviderError: 502,
}


def create_app(container: Container | None = None) -> FastAPI:
    resolved = container or build_container()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        resolved.jobs.shutdown()
        resolved.exports.shutdown()

    app = FastAPI(title="Velvet Dub", version=__version__, lifespan=lifespan)
    app.state.container = resolved
    app.add_middleware(LocalOnlyGuard, allowed_hosts=resolved.settings.allowed_hosts)
    # Added last, so it answers first. Only the web app's own addresses are approved, and only for
    # POST (the film upload, the one request sent straight to the API instead of through the web
    # app's proxy). Every other page is still refused, and the guard above still demands the
    # custom header, so nothing here lets another site drive the API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.settings.web_origins,
        allow_methods=["POST"],
        allow_headers=["X-Velvetdub-Client", "Content-Type"],
        allow_credentials=False,
    )

    @app.exception_handler(VelvetDubError)
    async def handle_domain_error(request: Request, exc: VelvetDubError) -> JSONResponse:
        for error_type, status in STATUS_FOR_ERROR.items():
            if isinstance(exc, error_type):
                return JSONResponse({"detail": str(exc)}, status_code=status)
        return JSONResponse({"detail": "Something went wrong."}, status_code=500)

    for router in (health, titles, playback, subtitles, media, exports):
        app.include_router(router.router, prefix="/api")
    return app
