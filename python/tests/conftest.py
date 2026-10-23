"""Shared test setup.

* Every test runs in memory unless it asks for the real services, so the suite never writes to the
  compose database by accident.
* When DATABASE_URL is set, the rows the tests wrote (run ids starting ``test-``) are cleared at the end.
"""
import os

import pytest

TABLES = ["actions", "refunds", "tickets", "orders", "customers"]


@pytest.fixture
def db():
    """A fresh in-memory database with the starting data, for one test."""
    from app.db.session import open_database

    with open_database("sqlite://")() as session:
        yield session


@pytest.fixture(autouse=True)
def _in_memory(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)


@pytest.fixture(scope="session", autouse=True)
def _clean_test_runs():
    yield
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        return
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        for table in TABLES:
            conn.execute(f"DELETE FROM {table} WHERE run_id LIKE 'test-%'")
