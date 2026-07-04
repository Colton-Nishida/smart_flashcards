"""Application settings, loaded from environment variables / .env."""

import logging
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SESSION_SECRET = "dev-insecure-session-secret"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    session_secret: str = DEFAULT_SESSION_SECRET
    data_dir: Path = BACKEND_DIR.parent / "data"

    @field_validator("data_dir", mode="after")
    @classmethod
    def _resolve_data_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    def model_post_init(self, __context: object) -> None:
        if self.session_secret == DEFAULT_SESSION_SECRET:
            logger.warning(
                "SESSION_SECRET is not set — using an insecure development default. "
                "Set SESSION_SECRET in the environment for anything beyond local dev."
            )


def get_settings() -> Settings:
    """Build settings from the current environment (call once per app)."""
    return Settings()
