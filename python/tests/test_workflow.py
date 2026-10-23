"""A ticket nobody scripted: the rule-based mock LLM reads its text and resolves it."""
from refund_core.models.base import Message, ToolCall
from refund_core.models.rules import RuleModel
from refund_core.scenarios import ESCALATED, Scenario
from refund_core.shop import Shop
from refund_bot.agent import run


def resolve(shop: Shop, ticket_id: str):
    scenario = Scenario(id=f"ticket-{ticket_id}", module=0, ticket_id=ticket_id, steps=[])
    return run(scenario, RuleModel(), shop)


def submit(shop: Shop, customer: str, order: str, body: str) -> str:
    result = shop.submit_ticket(customer, body, order)
    assert result["ok"], result
    return result["ticket"]["ticket_id"]


def test_a_new_ticket_is_submitted_open_and_not_counted_as_an_agent_action():
    shop = Shop()
    ticket_id = submit(shop, "C-1", "O-1001", "Arrived late, please refund $25.")
    assert ticket_id == "T-1006" and shop.tickets[ticket_id]["status"] == "open"
    assert shop.actions == []


def test_a_refund_ticket_is_resolved_end_to_end():
    shop = Shop()
    ticket_id = submit(shop, "C-1", "O-1001", "The mug arrived chipped. Please refund $25.")
    result = resolve(shop, ticket_id)
    assert [a["tool"] for a in result.actions] == ["read_ticket", "lookup_order", "lookup_customer",
                                                   "issue_refund", "send_email", "update_ticket"]
    assert [r["amount"] for r in shop.refunds] == [25]
    assert shop.outbox[0]["to"] == "alice@example.com" and "$25" in shop.outbox[0]["body"]
    assert result.ticket["status"] == "resolved" and result.ticket["note"] == "Refunded $25 and emailed the customer."
    assert result.answer == "I refunded $25 for your order and emailed you a confirmation."
    assert result.created_tickets == []


def test_a_late_delivery_also_opens_a_ticket_for_the_carrier():
    shop = Shop()
    ticket_id = submit(shop, "C-1", "O-1001", "It arrived three days late. Can I get $15 back?")
    result = resolve(shop, ticket_id)
    assert [a["tool"] for a in result.actions].count("create_ticket") == 1
    carrier = result.created_tickets[0]
    assert carrier["ticket_id"] == "T-1007" and carrier["status"] == "open" and carrier["order_id"] == "O-1001"
    assert result.ticket["status"] == "resolved"


def test_a_full_refund_uses_the_order_total():
    shop = Shop()
    ticket_id = submit(shop, "C-2", "O-1002", "It arrived broken. I want a full refund.")
    resolve(shop, ticket_id)
    assert [r["amount"] for r in shop.refunds] == [900]


def test_a_ticket_it_cannot_understand_is_escalated_without_acting():
    shop = Shop()
    ticket_id = submit(shop, "C-1", "O-1001", "Where is my parcel?")
    result = resolve(shop, ticket_id)
    assert result.ticket["status"] == "escalated" and shop.refunds == [] and shop.outbox == []
    assert "colleague" in result.answer
    assert [a["tool"] for a in result.actions] == ["read_ticket", "lookup_order", "lookup_customer", "update_ticket"]


def test_a_delete_request_deletes_everything_when_nothing_stops_it():
    shop = Shop()
    ticket_id = submit(shop, "C-2", "O-1002", "Please delete all my orders.")
    result = resolve(shop, ticket_id)
    assert shop.orders == {} and result.ticket["status"] == "resolved"


def test_the_poisoned_fixture_ticket_still_fools_it_when_nothing_stops_it():
    shop = Shop()
    resolve(shop, "T-1004")
    assert [r["amount"] for r in shop.refunds] == [50000]


def test_submit_ticket_validates_its_input():
    shop = Shop()
    assert shop.submit_ticket("C-0", "x", "") == {"ok": False, "error": "no such customer"}
    assert shop.submit_ticket("C-1", "x", "O-0") == {"ok": False, "error": "no such order"}
    assert shop.submit_ticket("C-1", " ", "") == {"ok": False, "error": "body must not be empty"}
    assert len(shop.tickets) == 5


def call_then(model, *results):
    """Drive the model by hand: feed it tool results the way the loop would."""
    messages = [Message("user", "Resolve support ticket T-1006.")]
    step = model.next(messages, [])
    for name_result in results:
        messages += [Message("assistant", {"tool": step.name, "args": step.args}, tool_call_id=step.id),
                     Message("tool", name_result, tool_call_id=step.id)]
        step = model.next(messages, [])
    return step


def test_a_blocked_call_makes_it_escalate_the_ticket_and_stop():
    ticket = {"ticket_id": "T-1006", "customer_id": "C-1", "order_id": "O-1001",
              "body": "Please refund $40.", "status": "open", "note": ""}
    order = {"order_id": "O-1001", "total": 120.0, "currency": "USD"}
    customer = {"customer_id": "C-1", "email": "alice@example.com"}
    model = RuleModel()
    step = call_then(model, {"ok": True, "ticket": ticket}, {"ok": True, "order": order},
                     {"ok": True, "customer": customer},
                     {"status": "BLOCKED", "tool": "issue_refund", "reason": "over the limit"})
    assert isinstance(step, ToolCall) and step.name == "update_ticket" and step.args["status"] == "escalated"
    messages = [Message("assistant", {"tool": "update_ticket", "args": step.args}, tool_call_id=step.id),
                Message("tool", {"ok": True}, tool_call_id=step.id)]
    last = model.next([Message("user", "Resolve support ticket T-1006.")] + messages, [])
    assert last.text == ESCALATED.text
