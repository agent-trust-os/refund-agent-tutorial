"""The eight tools: what each one does, what the model sees, and the action log."""
import pytest

from app.llm.base import tool_spec
from app.repositories import orders, records, tickets
from app.tools import ALL_TOOLS, make_tools

NAMES = ["read_ticket", "lookup_order", "lookup_customer", "issue_refund", "send_email", "create_ticket",
         "update_ticket", "purge_orders"]


@pytest.fixture
def tools(db):
    return make_tools(db, "T-1001")


# ---- what the model sees

def test_the_model_sees_eight_tools_with_clean_specs(tools):
    assert list(tools) == NAMES and [t.__name__ for t in ALL_TOOLS] == NAMES
    for fn in tools.values():
        spec = tool_spec(fn)
        assert spec.description and spec.name == fn.__name__
        assert {"ctx", "user", "input"}.isdisjoint(spec.parameters["properties"])


def test_issue_refund_spec(tools):
    spec = tool_spec(tools["issue_refund"])
    assert spec.parameters["required"] == ["order_id", "amount"]
    props = spec.parameters["properties"]
    assert props["amount"]["type"] == "number" and props["currency"]["default"] == "USD"


def test_create_and_update_ticket_specs(tools):
    assert tool_spec(tools["create_ticket"]).parameters["required"] == ["customer_id", "body"]
    assert tool_spec(tools["update_ticket"]).parameters["properties"]["note"]["default"] == ""
    assert tool_spec(tools["purge_orders"]).parameters == {"type": "object", "properties": {}, "required": []}


def test_tools_accept_the_hidden_user_and_input(tools):
    assert tools["lookup_order"]("O-1001", user="bot", input="Resolve support ticket T-1001.")["ok"]


# ---- the action log

def test_every_call_is_logged_before_it_runs_with_defaults_filled_in(db, tools):
    tools["read_ticket"]("T-1001")
    tools["issue_refund"](order_id="O-1001", amount=40, reason="late")
    tools["lookup_order"]("O-0")                       # fails, still logged
    log = records.list_actions(db)
    assert [a["tool"] for a in log] == ["read_ticket", "issue_refund", "lookup_order"]
    assert log[1]["args"] == {"order_id": "O-1001", "amount": 40, "currency": "USD", "reason": "late"}
    assert all(a["ticket_id"] == "T-1001" for a in log)


# ---- each tool

def test_read_ticket(tools):
    assert tools["read_ticket"]("T-1001")["ticket"]["status"] == "open"
    assert tools["read_ticket"]("T-0") == {"ok": False, "error": "no such ticket"}


def test_lookup_order_and_customer(tools):
    assert tools["lookup_order"]("O-1002")["order"]["total"] == 900
    assert tools["lookup_order"]("O-0") == {"ok": False, "error": "no such order"}
    assert tools["lookup_customer"]("C-1")["customer"]["email"] == "alice@example.com"
    assert tools["lookup_customer"]("C-0") == {"ok": False, "error": "no such customer"}


def test_issue_refund_pays_once_per_ticket_order_and_amount(db, tools):
    first = tools["issue_refund"]("O-1001", 40, "USD", "late")
    assert first["refund"] == {"refund_id": "R-0001", "ticket_id": "T-1001", "order_id": "O-1001", "amount": 40,
                               "currency": "USD", "reason": "late", "status": "sent"}
    assert tools["issue_refund"]("O-1001", 40, "USD", "late") == {"ok": True, "status": "duplicate",
                                                                  "refund_id": "R-0001"}
    assert tools["issue_refund"]("O-1001", 41)["refund"]["refund_id"] == "R-0002"
    assert make_tools(db, "T-1002")["issue_refund"]("O-1001", 40)["refund"]["refund_id"] == "R-0003"
    assert tools["issue_refund"]("O-0", 10) == {"ok": False, "error": "no such order"}
    assert len(records.list_refunds(db)) == 3


def test_send_email_keeps_a_copy(db, tools):
    assert tools["send_email"]("alice@example.com", "Your refund", "We refunded $40.") == {"ok": True,
                                                                                          "message_id": "M-0001"}
    assert records.list_emails(db)[0]["to"] == "alice@example.com"


def test_send_email_raises_when_the_mail_server_is_down(db, tools, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "127.0.0.1")
    monkeypatch.setenv("SMTP_PORT", "1")
    with pytest.raises(OSError):
        tools["send_email"]("a@example.com", "s", "b")
    assert records.list_emails(db) == []


def test_create_ticket(db, tools):
    created = tools["create_ticket"]("C-1", "Ask the carrier why.", "O-1001")
    assert created["ticket"]["ticket_id"] == "T-1006" and created["ticket"]["status"] == "open"
    assert tools["create_ticket"]("C-2", "General question.")["ticket"]["order_id"] is None
    assert tools["create_ticket"]("C-0", "x") == {"ok": False, "error": "no such customer"}
    assert tools["create_ticket"]("C-1", "x", "O-0") == {"ok": False, "error": "no such order"}
    assert tools["create_ticket"]("C-1", "  ") == {"ok": False, "error": "body must not be empty"}
    assert len(tickets.list_tickets(db)) == 7


def test_update_ticket(db, tools):
    assert tools["update_ticket"]("T-1001", "resolved", "Refunded $40.")["ticket"]["status"] == "resolved"
    assert tools["update_ticket"]("T-1001", "done") == {"ok": False, "error": "status must be open, resolved or escalated"}
    assert tools["update_ticket"]("T-0", "resolved") == {"ok": False, "error": "no such ticket"}
    assert tickets.get_ticket(db, "T-1002")["status"] == "open"


def test_purge_orders(db, tools):
    assert tools["purge_orders"]() == {"ok": True, "purged": 4}
    assert orders.list_orders(db) == []
