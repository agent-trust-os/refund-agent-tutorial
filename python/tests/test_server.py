import json
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
    assert [a["tool"] for a in body["actions"]] == ["read_ticket", "lookup_order", "issue_refund"]
    assert body["actions"][2]["args"]["amount"] == 5000
    assert body["transcript"][0]["role"] == "user"


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
