import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


def _load_dotenv() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()


class Settings(BaseSettings):
    workspace_path: Path = Path.home() / "Jarvis"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_prefix": "JARVIS_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
