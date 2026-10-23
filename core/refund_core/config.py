"""Build a Shop from the environment: in memory by default, Postgres when ``DATABASE_URL`` is set.

A setting that is present but cannot be reached fails loudly. It never falls back to memory,
because that would hide a broken setup.
"""
from __future__ import annotations

import os

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
    return Shop(store, run_id)
