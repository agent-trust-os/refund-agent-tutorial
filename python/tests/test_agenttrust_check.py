"""``refund-bot agenttrust check`` against the offline stub gateway."""
import pytest

from app.agenttrust_check import run_checks

from stub_gateway import GOOD_KEY, StubGateway


@pytest.fixture
def gateway():
    stub = StubGateway()
    yield stub
    stub.close()


def test_all_four_lines_pass(gateway):
    lines: list[str] = []
    assert run_checks(gateway.url, GOOD_KEY, "refund-bot", lines.append) is True
    assert [line[:2] for line in lines] == ["ok"] * 4
    assert [r["action"] for r in gateway.seen] == ["lookup_order", "issue_refund", "purge_orders"]


def test_wrong_key_says_so(gateway):
    lines: list[str] = []
    assert run_checks(gateway.url, "at_live_wrong", "refund-bot", lines.append) is False
    assert "rejected the key" in lines[-1]


def test_missing_settings_say_which_file(monkeypatch):
    monkeypatch.delenv("AGENTRUST_GATEWAY_URL", raising=False)
    monkeypatch.delenv("AGENTRUST_KEY", raising=False)
    lines: list[str] = []
    assert run_checks(out=lines.append) is False
    assert ".env-sample" in lines[0]


def test_unreachable_gateway():
    lines: list[str] = []
    assert run_checks("http://127.0.0.1:1", GOOD_KEY, "refund-bot", lines.append) is False
    assert "not reachable" in lines[0]
