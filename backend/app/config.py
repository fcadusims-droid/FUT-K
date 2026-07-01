"""Backend configuration.

``DATABASE_URL`` selects the engine: any SQLAlchemy URL works. Defaults to a
local SQLite file for zero-config development and CI (no external service
required); point it at Postgres in production, e.g.::

    postgresql+psycopg://fie_app:fie_dev_pw@localhost:5432/fie_dev
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = Field(
        default="sqlite:///./fie_backend.db", validation_alias="DATABASE_URL"
    )


def get_settings() -> Settings:
    return Settings()
