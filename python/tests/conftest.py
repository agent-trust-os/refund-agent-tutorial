"""Shared test setup.

Every test runs on its own in-memory database (the ``db`` fixture) with no mail server, whatever is set in
the environment. Tests that need the real Postgres or Mailpit read POSTGRES_TEST_URL or MAILPIT_API, which
only the compose ``test`` service sets.
"""
import pytest


@pytest.fixture
def db():
    """A fresh in-memory database with the starting data, for one test."""
    from app.db.session import open_database

    with open_database("sqlite://")() as session:
        yield session


@pytest.fixture(autouse=True)
def _no_real_services(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
