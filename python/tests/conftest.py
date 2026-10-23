"""Run every test in memory unless it asks for the real services, so the suite never writes to the
shared compose database by accident."""
import pytest


@pytest.fixture(autouse=True)
def _in_memory(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
