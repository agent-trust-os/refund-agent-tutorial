"""One contract suite for every Store. The Postgres run needs DATABASE_URL (the compose database)."""
import os
import uuid

import pytest

from refund_core.store import MemoryStore

DSN = os.environ.get("DATABASE_URL")
BACKENDS = ["memory", pytest.param("postgres", marks=pytest.mark.skipif(not DSN, reason="DATABASE_URL not set"))]


def run_id() -> str:
    return f"test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(params=BACKENDS)
def make_store(request):
    opened = []

    def make(rid: str | None = None):
        rid = rid or run_id()
        if request.param == "memory":
            store = MemoryStore()
        else:
            from refund_core.pgstore import PostgresStore

            store = PostgresStore(DSN, rid)
        opened.append(store)
        return store

    yield make
    for store in opened:
        store.close()


def test_reads_the_fixtures(make_store):
    store = make_store()
    assert store.get_order("O-1002")["total"] == 900
    assert store.get_customer("C-1")["ssn"].startswith("000-")
    assert store.get_ticket("T-1005")["order_id"] is None
    assert store.get_ticket("T-0") is None and store.get_order("O-0") is None and store.get_customer("C-0") is None


def test_money_comes_back_as_plain_numbers(make_store):
    order = make_store().get_order("O-1001")
    assert isinstance(order["total"], float) and order["delivered_late"] is True


def test_refund_is_idempotent_and_ids_count_up(make_store):
    store = make_store()
    assert store.find_refund("O-1001", 40) is None
    first = store.add_refund("O-1001", 40, "USD", "late")
    assert first == {"refund_id": "R-0001", "order_id": "O-1001", "amount": 40, "currency": "USD", "status": "sent"}
    assert store.find_refund("O-1001", 40) == "R-0001"
    assert store.add_refund("O-1001", 41, "USD", "late")["refund_id"] == "R-0002"
    assert [r["amount"] for r in store.refunds()] == [40, 41]


def test_actions_are_numbered_in_order(make_store):
    store = make_store()
    store.log_action("read_ticket", {"ticket_id": "T-1001"})
    store.log_action("issue_refund", {"order_id": "O-1001", "amount": 40})
    assert store.actions() == [
        {"seq": 1, "tool": "read_ticket", "args": {"ticket_id": "T-1001"}},
        {"seq": 2, "tool": "issue_refund", "args": {"order_id": "O-1001", "amount": 40}},
    ]


def test_purge_only_touches_this_run(make_store):
    mine, other = make_store(), make_store()
    assert mine.purge_orders() == 4
    assert mine.orders() == {} and mine.get_order("O-1001") is None
    assert other.get_order("O-1001") is not None and len(other.orders()) == 4


def test_runs_are_isolated(make_store):
    a, b = make_store(), make_store()
    a.add_refund("O-1001", 40, "USD", "late")
    a.log_action("issue_refund", {})
    assert b.refunds() == [] and b.actions() == []
    assert b.add_refund("O-1001", 40, "USD", "late")["refund_id"] == "R-0001"


@pytest.mark.skipif(not DSN, reason="DATABASE_URL not set")
def test_rows_survive_after_the_connection_closes():
    from refund_core.pgstore import PostgresStore

    rid = run_id()
    first = PostgresStore(DSN, rid)
    first.add_refund("O-1001", 40, "USD", "late")
    first.log_action("issue_refund", {"amount": 40})
    first.close()
    later = PostgresStore(DSN, rid, seed=False)
    try:
        assert [r["refund_id"] for r in later.refunds()] == ["R-0001"]
        assert [a["tool"] for a in later.actions()] == ["issue_refund"]
    finally:
        later.close()
