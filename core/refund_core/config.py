"""Build a Shop from the environment: in memory by default; Postgres when ``DATABASE_URL`` is set and
SMTP (Mailpit) when ``SMTP_HOST`` is set.

A setting that is present but cannot be reached fails loudly. It never falls back to memory,
because that would hide a broken setup.
"""
from __future__ import annotations

import os

from .mail import Mailer, MemoryMailer, SmtpMailer
from .shop import Shop, new_run_id
from .store import MemoryStore, Store


def new_shop(run_id: str | None = None) -> Shop:
    run_id = run_id or new_run_id()
    dsn = os.environ.get("DATABASE_URL")
    store: Store
    if dsn:
        from .pgstore import PostgresStore

        store = PostgresStore(dsn, run_id)
    else:
        store = MemoryStore()
    mailer: Mailer
    host = os.environ.get("SMTP_HOST")
    if host:
        mailer = SmtpMailer(host, int(os.environ.get("SMTP_PORT", "1025")),
                            os.environ.get("SMTP_FROM", "support@example.com"))
    else:
        mailer = MemoryMailer()
    return Shop(store, run_id, mailer)
