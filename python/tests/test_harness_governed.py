"""The Refund Bot with ``governed="harness"``, against the offline stub gateway (no network, no key)."""
import pytest
from stub_gateway import GOOD_KEY, StubGateway

from app.repositories import orders, records
from app.services.tickets import resolve_ticket
from app.tools.governance import GovernanceNotConfigured, governed_harness


@pytest.fixture
def gateway(monkeypatch):
    stub = StubGateway()
    monkeypatch.setenv("AGENTRUST_GATEWAY_URL", stub.url)
    monkeypatch.setenv("AGENTRUST_KEY", GOOD_KEY)
    monkeypatch.setenv("AGENTRUST_FAILURE_MODE", "closed")
    monkeypatch.setenv("AGENTRUST_RETRY_ATTEMPTS", "1")
    yield stub
    stub.close()


def actions(db, ticket_id):
    return [a["tool"] for a in records.list_actions(db, ticket_id=ticket_id)]


def test_a_normal_refund_runs_and_every_tool_is_checked(db, gateway):
    result = resolve_ticket(db, "T-1001", governed="harness")
    assert result.ticket["status"] == "resolved"
    assert "issue_refund" in actions(db, "T-1001")
    checked = [r["action"] for r in gateway.seen if r["path"].endswith("/pre-check")]
    assert checked[:3] == ["read_ticket", "lookup_order", "lookup_customer"] and "issue_refund" in checked
    assert any(r["path"].endswith("/post-check") for r in gateway.seen)


def test_a_5000_refund_is_blocked_before_it_runs(db, gateway):
    result = resolve_ticket(db, "T-1003", governed="harness")
    blocked = [m.content for m in result.transcript if m.role == "tool" and m.content.get("status") == "BLOCKED"]
    assert blocked and "amount above max_amount" in blocked[0]["reason"]
    assert "issue_refund" not in actions(db, "T-1003")          # it never ran, so it is not in the action log
    assert records.list_refunds(db) == []
    assert result.ticket["status"] == "escalated"


def test_purge_is_blocked_and_the_orders_survive(db, gateway):
    result = resolve_ticket(db, "T-1005", governed="harness")
    assert "purge_orders" not in actions(db, "T-1005")
    assert result.ticket["status"] == "escalated"
    assert len(orders.list_orders(db)) == 4


def test_an_unreachable_gateway_fails_closed(db, monkeypatch):
    monkeypatch.setenv("AGENTRUST_GATEWAY_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("AGENTRUST_KEY", GOOD_KEY)
    monkeypatch.setenv("AGENTRUST_FAILURE_MODE", "closed")
    monkeypatch.setenv("AGENTRUST_RETRY_ATTEMPTS", "1")
    result = resolve_ticket(db, "T-1001", governed="harness")
    assert any(m.role == "tool" and m.content.get("status") == "UNAVAILABLE" for m in result.transcript)
    assert actions(db, "T-1001") == []
    assert result.ticket["status"] == "open"        # even closing the ticket was refused: a person picks it up


def test_governed_mode_without_a_gateway_refuses_to_start(monkeypatch):
    monkeypatch.delenv("AGENTRUST_GATEWAY_URL", raising=False)
    monkeypatch.delenv("AGENTRUST_KEY", raising=False)
    with pytest.raises(GovernanceNotConfigured):
        governed_harness(lambda: {})


def test_no_ssn_or_card_in_lookup_customer(db):
    from app.tools import make_tools

    customer = make_tools(db, None)["lookup_customer"]("C-1")["customer"]
    assert "ssn" not in customer and "card_number" not in customer
