"""One ticket, end to end: a customer writes in, the agent resolves it, and every layer shows what happened.

Run it on its own in-memory database (no services needed) and watch each step:

    uv run pytest tests/test_end_to_end.py -s

Run the same story against the Docker stack (Postgres, Mailpit, the app on port 8000):

    docker compose up -d --wait
    E2E_BASE_URL=http://localhost:8000 MAILPIT_API=http://localhost:8025 uv run pytest tests/test_end_to_end.py -s

The path the ticket takes:

    POST /tickets                      routes/tickets.py   -> services/tickets.py submit_ticket()
    POST /tickets/{id}/resolve         routes/tickets.py   -> services/tickets.py resolve_ticket()
      agents/support_agent.py run()    the loop: asks the model, runs the tool it names, repeats
        llm/rules.py RuleModel.next()  reads the ticket and picks the next tool
        tools/__init__.py make_tools() writes the action log, then calls the tool
          tools/refunds.py etc.        the tool's own rules
            repositories/*.py          the database rows
"""
import json
import os
import urllib.error
import urllib.request

import pytest
from fastapi.testclient import TestClient

from app.db.session import open_database
from app.main import create_app

BASE_URL = os.environ.get("E2E_BASE_URL")          # set to run against a live server
MAILPIT_API = os.environ.get("MAILPIT_API")        # set to also check the email in Mailpit

TICKET = {"customer_id": "C-1", "order_id": "O-1001",
          "body": "My mug arrived chipped and three days late. Can I get $25 back?"}

# What the agent should do with that ticket, in order.
EXPECTED_TOOLS = ["read_ticket", "lookup_order", "lookup_customer", "issue_refund", "create_ticket",
                  "send_email", "update_ticket"]


# ---------------------------------------------------------------- talking to the app

class LiveClient:
    """The same three calls as FastAPI's TestClient, made over HTTP to a running server."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def request(self, method: str, path: str, json_body=None):
        data = json.dumps(json_body).encode() if json_body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)


class LocalClient:
    """FastAPI's TestClient on a fresh in-memory database."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def request(self, method: str, path: str, json_body=None):
        response = self.client.request(method, path, json=json_body)
        return response.status_code, response.json()


@pytest.fixture
def app():
    if BASE_URL:
        yield LiveClient(BASE_URL)
    else:
        with TestClient(create_app(open_database("sqlite://"))) as client:
            yield LocalClient(client)


def step(title: str) -> None:
    print(f"\n== {title}")


def mailpit(path: str, method: str = "GET"):
    req = urllib.request.Request(MAILPIT_API + path, method=method)
    with urllib.request.urlopen(req) as r:
        body = r.read().decode()
    return json.loads(body) if body.startswith(("{", "[")) else body


# ---------------------------------------------------------------- the test

def test_a_ticket_from_submission_to_resolution(app):
    if MAILPIT_API:
        mailpit("/api/v1/messages", "DELETE")

    # 1. A customer writes in. The ticket starts open, and the agent has done nothing yet.
    step("1. A customer writes in: POST /tickets")
    status, ticket = app.request("POST", "/tickets", TICKET)
    assert status == 201, ticket
    ticket_id = ticket["ticket_id"]
    print(f"   created {ticket_id}: status={ticket['status']}  body={ticket['body']!r}")
    assert ticket["status"] == "open" and ticket["note"] == ""
    assert app.request("GET", f"/actions?ticket_id={ticket_id}")[1] == []

    # 2. The agent resolves it. The response is the whole conversation between the model and the tools.
    step(f"2. The agent resolves it: POST /tickets/{ticket_id}/resolve")
    status, result = app.request("POST", f"/tickets/{ticket_id}/resolve")
    assert status == 200, result

    transcript = result["transcript"]
    assert transcript[0] == {"role": "user", "content": f"Resolve support ticket {ticket_id}.", "tool_call_id": None}
    calls = {m["tool_call_id"]: m["content"] for m in transcript if m["role"] == "assistant" and isinstance(m["content"], dict)}
    results = [(calls[m["tool_call_id"]], m["content"]) for m in transcript if m["role"] == "tool"]
    for n, (call, outcome) in enumerate(results, 1):
        print(f"   step {n}  {call['tool']}({json.dumps(call['args'])[1:-1][:70]})")
        print(f"           -> {json.dumps(outcome)[:90]}")
    print(f"   agent says: {result['answer']}")

    # Every step the model asked for ran, in order, and succeeded.
    assert [call["tool"] for call, _ in results] == EXPECTED_TOOLS
    assert all(outcome.get("ok") is True for _, outcome in results)
    # Every tool message answers the call just before it.
    for before, after in zip(transcript[1:-1:2], transcript[2:-1:2]):
        assert before["role"] == "assistant" and after["role"] == "tool"
        assert before["tool_call_id"] == after["tool_call_id"]
    assert transcript[-1] == {"role": "assistant", "content": result["answer"], "tool_call_id": None}
    assert result["answer"] == "I refunded $25 for your order and emailed you a confirmation."

    # 3. The ticket is resolved, with a note saying what was done.
    step("3. The ticket afterwards: GET /tickets/{id}")
    status, after = app.request("GET", f"/tickets/{ticket_id}")
    print(f"   {ticket_id}: status={after['status']}  note={after['note']!r}")
    assert after["status"] == "resolved"
    assert after["note"] == "Refunded $25 and emailed the customer."

    # 4. The action log matches the conversation exactly: same tools, same arguments, same order.
    step(f"4. The action log: GET /actions?ticket_id={ticket_id}")
    actions = app.request("GET", f"/actions?ticket_id={ticket_id}")[1]
    for n, a in enumerate(actions, 1):
        print(f"   {n}. {a['tool']} {json.dumps(a['args'])[:80]}")
    assert [(a["tool"], a["args"]) for a in actions] == [(c["tool"], c["args"]) for c, _ in results]

    # 5. Exactly one refund, for $25, linked to this ticket.
    step("5. The money: GET /refunds")
    refunds = [r for r in app.request("GET", "/refunds")[1] if r["ticket_id"] == ticket_id]
    print(f"   {refunds}")
    assert [(r["order_id"], r["amount"], r["status"]) for r in refunds] == [("O-1001", 25, "sent")]

    # 6. The late delivery made the agent open a follow-up ticket for the carrier.
    step("6. The follow-up ticket it created")
    created = result["created_tickets"]
    print(f"   {[(t['ticket_id'], t['status'], t['body']) for t in created]}")
    assert len(created) == 1 and created[0]["status"] == "open" and created[0]["order_id"] == "O-1001"
    assert "carrier" in created[0]["body"]

    # 7. One email to the customer, stored, and in Mailpit when the stack is running.
    step("7. The email: GET /emails (and Mailpit)")
    emails = [e for e in app.request("GET", "/emails")[1] if e["ticket_id"] == ticket_id]
    print(f"   stored: {[(e['to'], e['subject']) for e in emails]}")
    assert [(e["to"], e["subject"]) for e in emails] == [("alice@example.com", "Your refund")]
    assert "$25" in emails[0]["body"]
    if MAILPIT_API:
        messages = mailpit("/api/v1/messages")["messages"]
        print(f"   Mailpit: {[(m['To'][0]['Address'], m['Subject']) for m in messages]}")
        assert [(m["To"][0]["Address"], m["Subject"]) for m in messages] == [("alice@example.com", "Your refund")]

    # 8. Resolving it again is refused, and changes nothing.
    step("8. Resolve again: refused")
    status, again = app.request("POST", f"/tickets/{ticket_id}/resolve")
    print(f"   HTTP {status} {again}")
    assert (status, again) == (409, {"error": f"ticket {ticket_id} is already resolved"})
    assert len(app.request("GET", f"/actions?ticket_id={ticket_id}")[1]) == len(EXPECTED_TOOLS)
