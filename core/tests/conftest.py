"""Clear the rows the tests wrote (run ids starting ``test-``) from the shared compose database."""
import os

import pytest

TABLES = ["actions", "refunds", "tickets", "orders", "customers"]


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
