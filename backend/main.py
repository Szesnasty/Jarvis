from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from models.schemas import HealthResponse
from routers.chat import router as chat_router
from routers.graph import router as graph_router
from routers.memory import router as memory_router
from routers.preferences import router as preferences_router
from routers.sessions import router as sessions_router
from routers.specialists import router as specialists_router
from routers.workspace import router as workspace_router

APP_VERSION = "0.1.0"


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title="Jarvis API", version=APP_VERSION)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
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

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
