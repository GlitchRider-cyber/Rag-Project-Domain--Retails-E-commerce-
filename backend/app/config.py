"""Application settings loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings

# Locate potential .env locations: root of repo, backend dir, or current dir
_this_dir = Path(__file__).resolve().parent
_backend_dir = _this_dir.parent
_root_dir = _backend_dir.parent

_env_candidates = [
    str(_root_dir / ".env"),
    str(_backend_dir / ".env"),
    ".env",
]


class Settings(BaseSettings):
    """Central configuration – reads from env vars and .env file."""

    GEMINI_API_KEY: str = ""
    GEMINI_CHAT_MODEL: str = "gemini-4-hydrogen"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/aurelia"
    ADMIN_PASSWORD: str = "changeme"
    ALLOWED_ORIGINS: str = "http://localhost:5173"
    RETRIEVAL_TOP_K: int = 6
    RELEVANCE_THRESHOLD: float = 0.3

    @property
    def origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS split into a list."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    model_config = {
        "env_file": _env_candidates,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
