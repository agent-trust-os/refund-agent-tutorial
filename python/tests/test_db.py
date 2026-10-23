"""The database layer: migrations, starting data and the repository functions.

Runs on in-memory SQLite, and on Postgres too when POSTGRES_TEST_URL is set (the compose test service)."""
import os

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.core.config import normalize_database_url
from app.db.models import Base
from app.db.seed import reset_database
from app.db.session import open_database
from app.repositories import orders, records, tickets

POSTGRES = os.environ.get("POSTGRES_TEST_URL")
URLS = ["sqlite://", pytest.param(POSTGRES, marks=pytest.mark.skipif(not POSTGRES, reason="POSTGRES_TEST_URL not set"))]


@pytest.fixture(params=URLS)
def db(request):
    sessions = open_database(normalize_database_url(request.param))
    with sessions() as session:
        reset_database(session)
        yield session
        reset_database(session)


def test_a_new_database_has_the_starting_data(db):
    assert [t["ticket_id"] for t in tickets.list_tickets(db)] == ["T-1001", "T-1002", "T-1003", "T-1004", "T-1005"]
    assert all(t["status"] == "open" and t["note"] == "" for t in tickets.list_tickets(db))
    assert [o["order_id"] for o in orders.list_orders(db)] == ["O-1001", "O-1002", "O-1003", "O-1004"]
    assert orders.get_customer(db, "C-1")["ssn"].startswith("000-")
    assert records.list_refunds(db) == [] and records.list_emails(db) == [] and records.list_actions(db) == []


def test_money_comes_back_as_plain_numbers(db):
    order = orders.get_order(db, "O-1001")
    assert order["total"] == 120.0 and isinstance(order["total"], float) and order["delivered_late"] is True


def test_unknown_ids_return_none(db):
    assert tickets.get_ticket(db, "T-0") is None
    assert orders.get_order(db, "O-0") is None
    assert orders.get_customer(db, "C-0") is None
    assert tickets.update_ticket(db, "T-0", "resolved", "") is None


def test_new_tickets_are_numbered_after_the_highest(db):
    first = tickets.add_ticket(db, "C-1", "O-1001", "Please refund $25.")
    assert first == {"ticket_id": "T-1006", "customer_id": "C-1", "order_id": "O-1001",
                     "body": "Please refund $25.", "status": "open", "note": ""}
    assert tickets.add_ticket(db, "C-2", None, "Hi.")["ticket_id"] == "T-1007"
    assert [t["ticket_id"] for t in tickets.list_tickets(db, status="open")][-1] == "T-1007"


def test_update_ticket_and_filter_by_status(db):
    tickets.update_ticket(db, "T-1001", "resolved", "Refunded $40.")
    assert tickets.get_ticket(db, "T-1001")["status"] == "resolved"
    assert [t["ticket_id"] for t in tickets.list_tickets(db, status="resolved")] == ["T-1001"]


def test_refunds_are_found_by_ticket_order_and_amount(db):
    assert records.find_refund(db, "T-1001", "O-1001", 40) is None
    first = records.add_refund(db, "T-1001", "O-1001", 40, "USD", "late")
    assert first == {"refund_id": "R-0001", "ticket_id": "T-1001", "order_id": "O-1001", "amount": 40,
                     "currency": "USD", "reason": "late", "status": "sent"}
    assert records.find_refund(db, "T-1001", "O-1001", 40) == "R-0001"
    assert records.find_refund(db, "T-1002", "O-1001", 40) is None
    assert records.add_refund(db, "T-1001", "O-1001", 41, "USD", "late")["refund_id"] == "R-0002"


def test_the_action_log_keeps_order_and_argument_order(db):
    records.add_action(db, "T-1001", "issue_refund", {"order_id": "O-1001", "amount": 40, "currency": "USD"})
    records.add_action(db, None, "purge_orders", {})
    log = records.list_actions(db)
    assert [a["tool"] for a in log] == ["issue_refund", "purge_orders"]
    assert list(log[0]["args"]) == ["order_id", "amount", "currency"]
    assert [a["tool"] for a in records.list_actions(db, ticket_id="T-1001")] == ["issue_refund"]


def test_delete_all_orders(db):
    assert orders.delete_all_orders(db) == 4 and orders.list_orders(db) == []


def test_reset_puts_the_starting_data_back(db):
    orders.delete_all_orders(db)
    tickets.add_ticket(db, "C-1", None, "x")
    records.add_refund(db, "T-1001", "O-1001", 40, "USD", "")
    records.add_email(db, "T-1001", "a@example.com", "s", "b")
    reset_database(db)
    assert len(orders.list_orders(db)) == 4 and len(tickets.list_tickets(db)) == 5
    assert records.list_refunds(db) == [] and records.list_emails(db) == []


def test_the_migration_matches_the_models(db):
    """If a model changes without a new migration, this fails."""
    context = MigrationContext.configure(db.connection())
    assert compare_metadata(context, Base.metadata) == []
    assert "alembic_version" in inspect(db.connection()).get_table_names()
