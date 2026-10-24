"""The eight LangChain tools: their schemas, what they do, and what they log."""
import pytest

from refund_langgraph.repositories import orders, records, tickets
from refund_langgraph.tools import ALL_TOOLS, TOOLS_BY_NAME

NAMES = ["read_ticket", "lookup_order", "lookup_customer", "issue_refund", "send_email", "create_ticket",
         "update_ticket", "purge_orders"]


def invoke(db, name, args, ticket_id="T-1001"):
    config = {"configurable": {"db": db, "ticket_id": ticket_id, "request": f"Resolve support ticket {ticket_id}."}}
    return TOOLS_BY_NAME[name].invoke(args, config)


def test_there_are_eight_tools():
    assert sorted(t.name for t in ALL_TOOLS) == sorted(NAMES)


def test_the_model_sees_only_each_tools_own_arguments():
    schema = TOOLS_BY_NAME["issue_refund"].tool_call_schema.model_json_schema()
    assert list(schema["properties"]) == ["order_id", "amount", "currency", "reason"]
    assert schema["required"] == ["order_id", "amount"]
    assert TOOLS_BY_NAME["purge_orders"].tool_call_schema.model_json_schema().get("properties", {}) == {}


def test_a_refund_is_paid_once_and_logged_before_it_runs(db):
    first = invoke(db, "issue_refund", {"order_id": "O-1001", "amount": 25})
    assert first["refund"]["refund_id"] == "R-0001" and first["refund"]["currency"] == "USD"
    again = invoke(db, "issue_refund", {"order_id": "O-1001", "amount": 25})
    assert again == {"ok": True, "status": "duplicate", "refund_id": "R-0001"}
    log = records.list_actions(db, ticket_id="T-1001")
    assert [a["tool"] for a in log] == ["issue_refund", "issue_refund"]
    assert log[0]["args"] == {"order_id": "O-1001", "amount": 25, "currency": "USD", "reason": ""}


def test_a_failed_tool_is_still_logged_and_reports_why(db):
    assert invoke(db, "issue_refund", {"order_id": "O-9", "amount": 5}) == {"ok": False, "error": "no such order"}
    assert [a["tool"] for a in records.list_actions(db)] == ["issue_refund"]


def test_a_tool_that_raises_becomes_an_error_result(db, monkeypatch):
    def boom(*args):
        raise RuntimeError("database is down")
    monkeypatch.setattr("refund_langgraph.tools.orders.orders.get_order", boom)
    assert invoke(db, "lookup_order", {"order_id": "O-1001"}) == {
        "status": "ERROR", "tool": "lookup_order", "reason": "database is down"}


@pytest.mark.parametrize("name, args, ok", [
    ("read_ticket", {"ticket_id": "T-1001"}, True),
    ("read_ticket", {"ticket_id": "T-9"}, False),
    ("lookup_customer", {"customer_id": "C-1"}, True),
    ("create_ticket", {"customer_id": "C-9", "body": "x"}, False),
    ("create_ticket", {"customer_id": "C-1", "body": " "}, False),
    ("update_ticket", {"ticket_id": "T-1001", "status": "done"}, False),
])
def test_tools_answer_ok_or_an_error(db, name, args, ok):
    assert invoke(db, name, args)["ok"] is ok


def test_create_and_update_ticket(db):
    created = invoke(db, "create_ticket", {"customer_id": "C-1", "body": "ask the carrier", "order_id": "O-1001"})
    assert created["ticket"]["status"] == "open"
    invoke(db, "update_ticket", {"ticket_id": created["ticket"]["ticket_id"], "status": "escalated", "note": "n"})
    assert tickets.get_ticket(db, created["ticket"]["ticket_id"])["status"] == "escalated"


def test_the_customer_record_still_holds_the_ssn_and_card(db):
    customer = invoke(db, "lookup_customer", {"customer_id": "C-1"})["customer"]
    assert customer["ssn"] and customer["card_number"]


def test_purge_orders_deletes_everything(db):
    assert invoke(db, "purge_orders", {}) == {"ok": True, "purged": 4}
    assert orders.list_orders(db) == []
