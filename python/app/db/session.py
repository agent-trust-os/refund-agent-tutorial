"""Connect to the database and prepare it.

``open_database(url)`` creates the tables with Alembic (if they are not there yet) and adds the starting
data to an empty database. The CLI and the API both call it, so nobody has to run a migration by hand.
"""
from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from alembic import command
from fastapi import Request
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from ..core.config import get_settings
from .seed import seed

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        options: dict = {"connect_args": {"check_same_thread": False}}
        if ":memory:" in url or url in ("sqlite://", "sqlite:///"):
            # One in-memory database shared by every connection (tests, throwaway scenario runs).
            options["poolclass"] = StaticPool
        return create_engine(url, **options)
    return create_engine(url, pool_pre_ping=True)


def migrate(engine: Engine) -> None:
    """Bring the schema up to date (``alembic upgrade head``) on this engine."""
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ALEMBIC_INI.parent / "alembic"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def open_database(url: str | None = None) -> sessionmaker[Session]:
    """Migrate and seed the database at ``url`` (default: DATABASE_URL) and return a session factory."""
    engine = make_engine(url or get_settings().database_url)
    migrate(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions() as db:
        seed(db)
    return sessions


@lru_cache(maxsize=4)
def database(url: str) -> sessionmaker[Session]:
    """The app's database for ``url``, opened once per process."""
    return open_database(url)


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one database session per request, closed afterwards."""
    with request.app.state.sessions() as db:
        yield db
