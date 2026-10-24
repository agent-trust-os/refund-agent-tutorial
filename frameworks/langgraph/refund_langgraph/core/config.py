"""Settings, read from environment variables, with defaults that work on a laptop with nothing installed.

| Variable       | Default                    | Used for                                  |
|----------------|----------------------------|-------------------------------------------|
| DATABASE_URL   | sqlite:///refund_langgraph.db    | where tickets, orders and refunds live    |
| SMTP_HOST      | (empty: emails stay local) | the mail server, Mailpit in Docker        |
| SMTP_PORT      | 1025                       |                                           |
| SMTP_FROM      | support@example.com        | the sender of every email                 |
| LLM_PROVIDER   | mock                       | mock, anthropic, or auto (anthropic if ANTHROPIC_API_KEY is set) |
| LLM_MODEL      | claude-sonnet-5-5          | the model when the provider is anthropic  |
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    smtp_host: str
    smtp_port: int
    smtp_from: str
    llm_provider: str
    llm_model: str


def get_settings() -> Settings:
    """Read the settings now. Called when needed, so tests can change the environment."""
    return Settings(
        database_url=normalize_database_url(os.environ.get("DATABASE_URL", "sqlite:///refund_langgraph.db")),
        smtp_host=os.environ.get("SMTP_HOST", ""),
        smtp_port=int(os.environ.get("SMTP_PORT", "1025")),
        smtp_from=os.environ.get("SMTP_FROM", "support@example.com"),
        llm_provider=os.environ.get("LLM_PROVIDER", "mock"),
        llm_model=os.environ.get("LLM_MODEL", "claude-sonnet-5-5"),
    )


def normalize_database_url(url: str) -> str:
    """SQLAlchemy reads ``postgresql://`` as the old psycopg2 driver; we use psycopg 3."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url
