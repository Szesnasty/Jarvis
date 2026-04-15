import logging
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from models.database import init_database
from models.schemas import HealthResponse
from routers.chat import router as chat_router
from routers.graph import router as graph_router
from routers.memory import router as memory_router
from routers.preferences import router as preferences_router
from routers.sessions import router as sessions_router
from routers.settings import router as settings_router
from routers.specialists import router as specialists_router
from routers.workspace import router as workspace_router

logger = logging.getLogger(__name__)

try:
    APP_VERSION = version("jarvis-backend")
except PackageNotFoundError:
    APP_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db_path = settings.workspace_path / "app" / "jarvis.db"
    if db_path.parent.exists():
        await init_database(db_path)
        # Reindex memory files so the DB stays in sync with files on disk
        from services.memory_service import reindex_all
        count = await reindex_all()
        if count > 0:
            logger.info("Startup reindex: %d notes indexed", count)
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Jarvis API", version=APP_VERSION, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", version=APP_VERSION)

    app.include_router(workspace_router)
    app.include_router(memory_router)
    app.include_router(chat_router)
    app.include_router(sessions_router)
    app.include_router(preferences_router)
    app.include_router(graph_router)
    app.include_router(specialists_router)
    app.include_router(settings_router)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
