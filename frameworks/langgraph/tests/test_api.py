"""The web app, end to end, on an in-memory database."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from refund_langgraph.db.session import open_database
from refund_langgraph.main import create_app


@pytest.fixture
def client():
    with TestClient(create_app(open_database("sqlite://"))) as client:
        yield client


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_the_starting_data(client):
    assert [t["ticket_id"] for t in client.get("/tickets").json()] == ["T-1001", "T-1002", "T-1003", "T-1004", "T-1005"]
    assert len(client.get("/orders").json()) == 4 and len(client.get("/customers").json()) == 3
    assert client.get("/refunds").json() == [] and client.get("/emails").json() == []


def test_a_ticket_goes_from_submitted_to_resolved(client):
    created = client.post("/tickets", json={"customer_id": "C-1", "order_id": "O-1001",
                                            "body": "The mug arrived chipped. Please refund $25."})
    assert created.status_code == 201 and created.json()["ticket_id"] == "T-1006"
    assert client.get("/tickets/T-1006").json()["status"] == "open"

    result = client.post("/tickets/T-1006/resolve").json()
    assert [a["tool"] for a in result["actions"]] == ["read_ticket", "lookup_order", "lookup_customer",
                                                      "issue_refund", "send_email", "update_ticket"]
    assert result["ticket"]["status"] == "resolved"
    assert result["ticket"]["note"] == "Refunded $25 and emailed the customer."
    assert result["transcript"][0] == {"role": "user", "content": "Resolve support ticket T-1006.", "tool_call_id": None}

    assert client.get("/tickets/T-1006").json()["status"] == "resolved"
    assert [t["ticket_id"] for t in client.get("/tickets", params={"status": "resolved"}).json()] == ["T-1006"]
    assert [(r["ticket_id"], r["amount"]) for r in client.get("/refunds").json()] == [("T-1006", 25)]
    assert client.get("/emails").json()[0]["to"] == "alice@example.com"
    assert len(client.get("/actions", params={"ticket_id": "T-1006"}).json()) == 6


def test_a_delete_request_empties_the_orders_and_reset_brings_them_back(client):
    client.post("/tickets", json={"customer_id": "C-2", "body": "Please delete all my orders."})
    client.post("/tickets/T-1006/resolve")
    assert client.get("/orders").json() == []
    assert client.post("/reset").json() == {"status": "reset"}
    assert len(client.get("/orders").json()) == 4 and len(client.get("/tickets").json()) == 5


def test_a_ticket_it_cannot_understand_is_escalated(client):
    client.post("/tickets", json={"customer_id": "C-1", "order_id": "O-1001", "body": "Where is my parcel?"})
    result = client.post("/tickets/T-1006/resolve").json()
    assert result["ticket"]["status"] == "escalated" and client.get("/refunds").json() == []


def test_scenarios_run_on_their_own_database(client):
    assert [s["id"] for s in client.get("/scenarios").json()][:2] == ["allowed_refund", "over_limit"]
    result = client.post("/scenarios/purge/run").json()
    assert [a["tool"] for a in result["actions"]] == ["read_ticket", "purge_orders", "update_ticket"]
    assert len(client.get("/orders").json()) == 4


@pytest.mark.parametrize("method, path, body, status, error", [
    ("post", "/tickets", {"customer_id": "C-9", "body": "hi"}, 400, "no such customer"),
    ("post", "/tickets", {"customer_id": "C-1", "order_id": "O-9", "body": "hi"}, 400, "no such order"),
    ("post", "/tickets", {"customer_id": "C-1", "body": "   "}, 400, "body must not be empty"),
    ("post", "/tickets", {"customer_id": "C-1"}, 400, "body is required"),
    ("post", "/tickets", [1], 400, "the request body must be a JSON object (send it with Content-Type: application/json)"),
    ("get", "/tickets/T-9999", None, 404, "no such ticket 'T-9999'"),
    ("post", "/tickets/T-9999/resolve", None, 404, "no such ticket 'T-9999'"),
    ("post", "/scenarios/nope/run", None, 404, "unknown scenario 'nope'"),
    ("get", "/nowhere", None, 404, "not found"),
])
def test_errors(client, method, path, body, status, error):
    response = getattr(client, method)(path, **({"json": body} if body is not None else {}))
    assert (response.status_code, response.json()) == (status, {"error": error})


def test_a_form_body_explains_how_to_send_json(client):
    response = client.post("/tickets", content="customer_id=C-1&body=hi",
                           headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert response.status_code == 400 and "Content-Type: application/json" in response.json()["error"]


def test_resolving_twice_is_a_conflict(client):
    client.post("/tickets/T-1005/resolve")
    response = client.post("/tickets/T-1005/resolve")
    assert (response.status_code, response.json()) == (409, {"error": "ticket T-1005 is already resolved"})


def test_a_database_that_goes_away_is_a_503(client, monkeypatch):
    def down(*args, **kwargs):
        raise OperationalError("SELECT", {}, Exception("connection refused"))
    monkeypatch.setattr("refund_langgraph.repositories.tickets.list_tickets", down)
    response = client.get("/tickets")
    assert response.status_code == 503 and "database unavailable" in response.json()["error"]
