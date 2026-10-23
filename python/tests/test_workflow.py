"""A ticket nobody scripted: a customer writes in, the rule-based mock LLM reads it and resolves it."""
import pytest

from app.agents.support_agent import run
from app.llm.base import Message, ToolCall
from app.llm.rules import RuleModel
from app.llm.scenarios import ESCALATED
from app.repositories import orders, records, tickets
from app.services.tickets import TicketError, resolve_ticket, submit_ticket


def tools_used(result):
    return [a["tool"] for a in result.actions]


def test_a_submitted_ticket_starts_open_and_is_not_an_agent_action(db):
    ticket = submit_ticket(db, "C-1", "Arrived late, please refund $25.", "O-1001")
    assert ticket["ticket_id"] == "T-1006" and ticket["status"] == "open"
    assert records.list_actions(db) == []


def test_a_refund_ticket_is_resolved_end_to_end(db):
    ticket_id = submit_ticket(db, "C-1", "The mug arrived chipped. Please refund $25.", "O-1001")["ticket_id"]
    result = resolve_ticket(db, ticket_id)
    assert tools_used(result) == ["read_ticket", "lookup_order", "lookup_customer", "issue_refund", "send_email",
                                  "update_ticket"]
    assert [(r["ticket_id"], r["amount"]) for r in records.list_refunds(db)] == [("T-1006", 25)]
    email = records.list_emails(db)[0]
    assert email["to"] == "alice@example.com" and "$25" in email["body"]
    assert result.ticket["status"] == "resolved" and result.ticket["note"] == "Refunded $25 and emailed the customer."
    assert result.answer == "I refunded $25 for your order and emailed you a confirmation."
    assert result.created_tickets == []


def test_a_late_delivery_also_opens_a_ticket_for_the_carrier(db):
    ticket_id = submit_ticket(db, "C-1", "It arrived three days late. Can I get $15 back?", "O-1001")["ticket_id"]
    result = resolve_ticket(db, ticket_id)
    assert tools_used(result).count("create_ticket") == 1
    carrier = result.created_tickets[0]
    assert carrier["ticket_id"] == "T-1007" and carrier["status"] == "open" and carrier["order_id"] == "O-1001"
    assert result.ticket["status"] == "resolved"


def test_a_full_refund_uses_the_order_total(db):
    ticket_id = submit_ticket(db, "C-2", "It arrived broken. I want a full refund.", "O-1002")["ticket_id"]
    resolve_ticket(db, ticket_id)
    assert [r["amount"] for r in records.list_refunds(db)] == [900]


def test_a_ticket_it_cannot_understand_is_escalated_without_acting(db):
    ticket_id = submit_ticket(db, "C-1", "Where is my parcel?", "O-1001")["ticket_id"]
    result = resolve_ticket(db, ticket_id)
    assert result.ticket["status"] == "escalated" and "colleague" in result.answer
    assert records.list_refunds(db) == [] and records.list_emails(db) == []
    assert tools_used(result) == ["read_ticket", "lookup_order", "lookup_customer", "update_ticket"]


def test_a_delete_request_deletes_everything_when_nothing_stops_it(db):
    ticket_id = submit_ticket(db, "C-2", "Please delete all my orders.", "O-1002")["ticket_id"]
    result = resolve_ticket(db, ticket_id)
    assert orders.list_orders(db) == [] and result.ticket["status"] == "resolved"


def test_the_poisoned_starting_ticket_still_fools_it_when_nothing_stops_it(db):
    resolve_ticket(db, "T-1004")
    assert [r["amount"] for r in records.list_refunds(db)] == [50000]


def test_submit_ticket_validates_its_input(db):
    for args, message in [(("C-0", "x"), "no such customer"), (("C-1", "x", "O-0"), "no such order"),
                          (("C-1", " "), "body must not be empty")]:
        with pytest.raises(TicketError) as err:
            submit_ticket(db, *args)
        assert err.value.message == message and err.value.status == 400
    assert len(tickets.list_tickets(db)) == 5


def test_resolve_refuses_unknown_and_closed_tickets(db):
    with pytest.raises(TicketError) as err:
        resolve_ticket(db, "T-9999")
    assert err.value.status == 404
    resolve_ticket(db, "T-1001")
    with pytest.raises(TicketError) as err:
        resolve_ticket(db, "T-1001")
    assert err.value.status == 409 and err.value.message == "ticket T-1001 is already resolved"


def test_a_blocked_call_makes_it_escalate_the_ticket_and_stop():
    ticket = {"ticket_id": "T-1006", "customer_id": "C-1", "order_id": "O-1001",
              "body": "Please refund $40.", "status": "open", "note": ""}
    results = [{"ok": True, "ticket": ticket}, {"ok": True, "order": {"order_id": "O-1001", "currency": "USD"}},
               {"ok": True, "customer": {"customer_id": "C-1", "email": "alice@example.com"}},
               {"status": "BLOCKED", "tool": "issue_refund", "reason": "over the limit"}]
    model, messages = RuleModel(), [Message("user", "Resolve support ticket T-1006.")]
    step = model.next(messages, [])
    for content in results:
        messages += [Message("assistant", {"tool": step.name, "args": step.args}, tool_call_id=step.id),
                     Message("tool", content, tool_call_id=step.id)]
        step = model.next(messages, [])
    assert isinstance(step, ToolCall) and step.name == "update_ticket" and step.args["status"] == "escalated"
    messages += [Message("assistant", {"tool": step.name, "args": step.args}, tool_call_id=step.id),
                 Message("tool", {"ok": True}, tool_call_id=step.id)]
    assert model.next(messages, []).text == ESCALATED.text
