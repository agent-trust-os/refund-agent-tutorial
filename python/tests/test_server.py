import json
import os
import threading
import urllib.error
import urllib.request

import pytest

from refund_bot.__main__ import main
from refund_bot.server import make_server


@pytest.fixture
def base_url():
    server = make_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, json.load(r)


def post(url):
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_health(base_url):
    assert get(base_url + "/health") == (200, {"status": "ok"})


def test_root_describes_the_app(base_url):
    status, body = get(base_url + "/")
    assert status == 200 and body["app"] == "refund-bot"
    assert "POST /run/{scenario}" in body["endpoints"]


def test_lists_scenarios(base_url):
    status, body = get(base_url + "/scenarios")
    assert status == 200
    assert [s["id"] for s in body][:2] == ["allowed_refund", "over_limit"]
    assert {"id", "module", "ticket_id"} == set(body[0])


def test_run_returns_the_answer_and_the_action_log(base_url):
    status, body = post(base_url + "/run/over_limit")
    assert status == 200
    assert body["scenario"] == "over_limit"
    assert body["answer"] == "Your refund of $5,000 has been sent."
    assert [a["tool"] for a in body["actions"]] == ["read_ticket", "lookup_order", "issue_refund", "update_ticket"]
    assert body["actions"][2]["args"]["amount"] == 5000
    assert body["transcript"][0]["role"] == "user"


def test_run_reports_the_ticket(base_url):
    body = post(base_url + "/run/allowed_refund")[1]
    assert body["ticket"] == {"ticket_id": "T-1001", "customer_id": "C-1", "order_id": "O-1001",
                              "body": "My order arrived five days late. Can I get $40 back?",
                              "status": "resolved", "note": "Refunded $40 and emailed the customer."}


def test_run_reports_created_tickets(base_url):
    body = post(base_url + "/run/follow_up")[1]
    assert [t["ticket_id"] for t in body["created_tickets"]] == ["T-1006"]
    assert body["created_tickets"][0]["status"] == "open"
    assert post(base_url + "/run/allowed_refund")[1]["created_tickets"] == []


def test_every_run_starts_from_a_fresh_shop(base_url):
    first = post(base_url + "/run/purge")[1]
    second = post(base_url + "/run/purge")[1]
    assert first["actions"] == second["actions"]
    after = post(base_url + "/run/allowed_refund")[1]
    assert [a["tool"] for a in after["actions"]][:2] == ["read_ticket", "lookup_order"]


def test_unknown_scenario_and_route_are_404_json(base_url):
    assert post(base_url + "/run/nope") == (404, {"error": "unknown scenario 'nope'"})
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(base_url + "/nowhere")
    assert err.value.code == 404 and json.load(err.value) == {"error": "not found"}


def test_serve_flag_starts_the_server(monkeypatch):
    called = {}
    monkeypatch.setattr("refund_bot.server.serve", lambda host, port: called.update(host=host, port=port))
    assert main(["--serve", "--host", "0.0.0.0", "--port", "9000"]) == 0
    assert called == {"host": "0.0.0.0", "port": 9000}


def test_an_unreachable_database_is_a_503_not_a_fallback(base_url, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/z?connect_timeout=2")
    status, body = post(base_url + "/run/over_limit")
    assert status == 503 and "DATABASE_URL" in body["error"]


def test_run_returns_a_run_id(base_url):
    first = post(base_url + "/run/allowed_refund")[1]
    second = post(base_url + "/run/allowed_refund")[1]
    assert first["run_id"].startswith("run-") and first["run_id"] != second["run_id"]


REAL_DSN = os.environ.get("DATABASE_URL")  # read at import, before the fixture in conftest.py clears it


@pytest.mark.skipif(not REAL_DSN, reason="DATABASE_URL not set")
def test_the_ticket_status_is_saved_in_postgres(base_url, monkeypatch):
    import psycopg

    monkeypatch.setenv("DATABASE_URL", REAL_DSN)
    body = post(base_url + "/run/allowed_refund")[1]
    run_id = body["run_id"]
    with psycopg.connect(REAL_DSN, autocommit=True) as conn:
        try:
            row = conn.execute("SELECT status, note FROM tickets WHERE run_id = %s AND ticket_id = 'T-1001'",
                               (run_id,)).fetchone()
            others = conn.execute("SELECT count(*) FROM tickets WHERE run_id = %s AND status = 'open'",
                                  (run_id,)).fetchone()[0]
        finally:
            for table in ["actions", "refunds", "tickets", "orders", "customers"]:
                conn.execute(f"DELETE FROM {table} WHERE run_id = %s", (run_id,))
    assert row == ("resolved", "Refunded $40 and emailed the customer.")
    assert others == 4


# ---- the ticket workflow: create a run, submit a ticket, watch the agent resolve it ----

def post_json(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def get_json(url):
    try:
        return get(url)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_a_ticket_goes_from_submitted_to_resolved(base_url):
    status, run = post(base_url + "/runs")
    assert status == 201 and run["run_id"].startswith("run-")
    assert [t["ticket_id"] for t in run["tickets"]] == ["T-1001", "T-1002", "T-1003", "T-1004", "T-1005"]
    assert {"order_id", "customer_id", "total"} == set(run["orders"][0])
    rid = run["run_id"]

    status, created = post_json(f"{base_url}/runs/{rid}/tickets",
                                {"customer_id": "C-1", "order_id": "O-1001",
                                 "body": "The mug arrived chipped. Please refund $25."})
    assert status == 201 and created["ticket"]["ticket_id"] == "T-1006" and created["ticket"]["status"] == "open"

    assert get_json(f"{base_url}/runs/{rid}/tickets/T-1006")[1]["ticket"]["status"] == "open"
    status, resolved = post(f"{base_url}/runs/{rid}/tickets/T-1006/resolve")
    assert status == 200
    assert resolved["ticket"]["status"] == "resolved"
    assert resolved["ticket"]["note"] == "Refunded $25 and emailed the customer."
    assert [a["tool"] for a in resolved["actions"]] == ["read_ticket", "lookup_order", "lookup_customer",
                                                        "issue_refund", "send_email", "update_ticket"]

    after = get_json(f"{base_url}/runs/{rid}/tickets/T-1006")[1]["ticket"]
    assert after["status"] == "resolved"
    state = get_json(f"{base_url}/runs/{rid}")[1]
    assert state["tickets"]["T-1006"]["status"] == "resolved" and state["tickets"]["T-1001"]["status"] == "open"
    assert [r["amount"] for r in state["refunds"]] == [25]
    assert len(state["actions"]) == 6


def test_a_ticket_that_cannot_be_understood_is_escalated(base_url):
    rid = post(base_url + "/runs")[1]["run_id"]
    post_json(f"{base_url}/runs/{rid}/tickets", {"customer_id": "C-1", "order_id": "O-1001", "body": "Where is my parcel?"})
    resolved = post(f"{base_url}/runs/{rid}/tickets/T-1006/resolve")[1]
    assert resolved["ticket"]["status"] == "escalated" and "colleague" in resolved["answer"]
    assert get_json(f"{base_url}/runs/{rid}")[1]["refunds"] == []


def test_runs_are_separate_workspaces(base_url):
    a = post(base_url + "/runs")[1]["run_id"]
    b = post(base_url + "/runs")[1]["run_id"]
    post_json(f"{base_url}/runs/{a}/tickets", {"customer_id": "C-1", "body": "Please refund $5."})
    assert len(get_json(f"{base_url}/runs/{a}")[1]["tickets"]) == 6
    assert len(get_json(f"{base_url}/runs/{b}")[1]["tickets"]) == 5


def test_workflow_errors(base_url):
    rid = post(base_url + "/runs")[1]["run_id"]
    assert get_json(base_url + "/runs/run-nope")[0] == 404
    assert post(base_url + "/runs/run-nope/tickets/T-1001/resolve")[0] == 404
    assert post_json(f"{base_url}/runs/{rid}/tickets", {"customer_id": "C-0", "body": "x"}) == (400, {"error": "no such customer"})
    assert post_json(f"{base_url}/runs/{rid}/tickets", {"customer_id": "C-1"}) == (400, {"error": "body is required"})
    assert post_json(f"{base_url}/runs/{rid}/tickets", [1])[0] == 400
    assert get_json(f"{base_url}/runs/{rid}/tickets/T-9999")[0] == 404
    assert post(f"{base_url}/runs/{rid}/tickets/T-9999/resolve")[0] == 404
    assert post(f"{base_url}/runs/{rid}/tickets/T-1001/resolve")[0] == 200
    status, body = post(f"{base_url}/runs/{rid}/tickets/T-1001/resolve")
    assert status == 409 and "already" in body["error"]


@pytest.mark.skipif(not REAL_DSN, reason="DATABASE_URL not set")
def test_the_workflow_survives_between_requests_in_postgres(base_url, monkeypatch):
    import psycopg

    monkeypatch.setenv("DATABASE_URL", REAL_DSN)
    rid = post(base_url + "/runs")[1]["run_id"]
    post_json(f"{base_url}/runs/{rid}/tickets", {"customer_id": "C-1", "order_id": "O-1001", "body": "Please refund $25."})
    post(f"{base_url}/runs/{rid}/tickets/T-1006/resolve")
    state = get_json(f"{base_url}/runs/{rid}")[1]
    with psycopg.connect(REAL_DSN, autocommit=True) as conn:
        row = conn.execute("SELECT status FROM tickets WHERE run_id = %s AND ticket_id = 'T-1006'", (rid,)).fetchone()
        for table in ["actions", "refunds", "tickets", "orders", "customers"]:
            conn.execute(f"DELETE FROM {table} WHERE run_id = %s", (rid,))
    assert row == ("resolved",) and state["tickets"]["T-1006"]["status"] == "resolved"
    assert get_json(base_url + "/runs/run-nope")[0] == 404
