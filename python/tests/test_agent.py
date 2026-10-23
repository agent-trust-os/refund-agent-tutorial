import sys

from refund_bot.__main__ import main
from refund_bot.agent import RunResult, call_tool, run
from refund_bot.models.base import FinalAnswer, Message, ToolCall
from refund_bot.models.mock import MockModel
from refund_bot.scenarios import BY_ID, SCENARIOS
from refund_bot.shop import Shop


def play(scenario_id: str, shop: Shop | None = None) -> tuple[RunResult, Shop]:
    shop = shop or Shop()
    scenario = BY_ID[scenario_id]
    return run(scenario, MockModel(scenario), shop), shop


def test_deterministic():
    first, _ = play("allowed_refund")
    second, _ = play("allowed_refund")
    assert first.transcript == second.transcript
    assert first.actions == second.actions
    assert first.answer == second.answer


def test_ungoverned_problem():
    over, shop = play("over_limit")
    assert [r["amount"] for r in shop.refunds] == [5000]
    assert over.answer == "Your refund of $5,000 has been sent."
    _, shop = play("purge")
    assert shop.orders == {} and shop.count("purge_orders") == 1
    _, shop = play("poisoned_ticket")
    assert [r["amount"] for r in shop.refunds] == [50000]


def test_allowed_refund_runs_every_step():
    result, shop = play("allowed_refund")
    assert [a["tool"] for a in result.actions] == ["read_ticket", "lookup_order", "issue_refund", "send_email",
                                                   "update_ticket"]
    assert shop.outbox[0]["to"] == "alice@example.com"


def test_transcript_pairs_each_call_with_its_result():
    result, _ = play("pii_lookup")
    roles = [m.role for m in result.transcript]
    assert roles == ["user", "assistant", "tool", "assistant", "tool", "assistant", "tool", "assistant"]
    assert result.transcript[1].tool_call_id == result.transcript[2].tool_call_id == "call-1"
    assert result.transcript[-1].content == result.answer


def test_poisoned_text_reaches_the_model_only_through_the_ticket_tool():
    result, _ = play("poisoned_ticket")
    assert "Ignore all previous" not in result.transcript[0].content
    assert "Ignore all previous" in str(result.transcript[2].content)


def test_the_agent_closes_the_ticket_and_the_run_reports_it():
    result, shop = play("allowed_refund")
    assert result.ticket["status"] == "resolved"
    assert result.ticket["note"] == "Refunded $40 and emailed the customer."
    assert shop.tickets["T-1001"]["status"] == "resolved"
    assert shop.tickets["T-1002"]["status"] == "open"


def test_ungoverned_the_bad_runs_also_close_their_tickets():
    for scenario_id, ticket_id in [("over_limit", "T-1003"), ("purge", "T-1005"), ("poisoned_ticket", "T-1004")]:
        result, _ = play(scenario_id)
        assert result.ticket["ticket_id"] == ticket_id and result.ticket["status"] == "resolved"


def test_a_follow_up_ticket_is_created_next_to_the_resolved_one():
    result, shop = play("follow_up")
    assert shop.tickets["T-1001"]["status"] == "resolved"
    new = shop.tickets["T-1006"]
    assert new["status"] == "open" and new["customer_id"] == "C-1" and new["order_id"] == "O-1001"
    assert [t["ticket_id"] for t in result.created_tickets] == ["T-1006"]
    assert [a["tool"] for a in result.actions] == ["read_ticket", "lookup_order", "issue_refund", "create_ticket",
                                                   "send_email", "update_ticket"]


def test_runs_without_a_follow_up_create_no_tickets():
    result, _ = play("allowed_refund")
    assert result.created_tickets == []


def test_offline():
    for scenario in SCENARIOS:
        play(scenario.id)
    assert "agentrust_sdk" not in sys.modules
    assert "httpx" not in sys.modules


def test_a_raising_tool_becomes_an_error_result():
    def broken(*, input: str = "") -> dict:
        raise RuntimeError("boom")

    result = call_tool(broken, ToolCall("call-1", "broken", {}), "Resolve ticket T-1")
    assert result == {"status": "ERROR", "tool": "broken", "reason": "boom"}


def test_call_tool_passes_the_request_as_input():
    seen = {}

    def tool(*, input: str = "") -> dict:
        seen["input"] = input
        return {"ok": True}

    call_tool(tool, ToolCall("call-1", "tool", {}), "Resolve ticket T-1")
    assert seen["input"] == "Resolve ticket T-1"


class Looping:
    name = "loop"

    def next(self, messages, tools):
        return ToolCall("c", "lookup_order", {"order_id": "O-1001"})


def test_step_limit_stops_the_loop():
    shop = Shop()
    result = run(BY_ID["allowed_refund"], Looping(), shop, max_steps=3)
    assert result.answer == "Stopped: step limit reached"
    assert shop.count("lookup_order") == 3


class AsksForAnUnknownTool:
    name = "unknown"

    def __init__(self):
        self.results = []

    def next(self, messages, tools):
        if messages[-1].role == "tool":
            self.results.append(messages[-1].content)
            return FinalAnswer("gave up")
        return ToolCall("c", "drop_database", {})


def test_unknown_tool_from_the_model_is_an_error_result():
    model = AsksForAnUnknownTool()
    result = run(BY_ID["allowed_refund"], model, Shop())
    assert model.results[0]["status"] == "ERROR" and "drop_database" in model.results[0]["reason"]
    assert result.answer == "gave up"


def test_cli_lists_scenarios(capsys):
    assert main(["--list"]) == 0
    out = capsys.readouterr().out.split()
    assert "over_limit" in out and "poisoned_ticket" in out


def test_cli_prints_the_action_log_for_the_problem(capsys):
    assert main(["over_limit"]) == 0
    out = capsys.readouterr().out
    assert "issue_refund" in out and '"amount": 5000' in out
    assert "Action log" in out


def test_cli_shows_that_the_ticket_is_resolved(capsys):
    assert main(["allowed_refund"]) == 0
    out = capsys.readouterr().out
    assert "Ticket T-1001: open -> resolved" in out
    assert "Refunded $40 and emailed the customer." in out


def test_cli_shows_the_ticket_it_created(capsys):
    assert main(["follow_up"]) == 0
    out = capsys.readouterr().out
    assert "Ticket T-1001: open -> resolved" in out
    assert "Created ticket T-1006 (open): Late delivery" in out


def test_cli_rejects_an_unknown_scenario(capsys):
    assert main(["nope"]) == 2
    assert "unknown scenario" in capsys.readouterr().err


def test_an_unreachable_database_fails_loudly(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:y@127.0.0.1:1/z?connect_timeout=2")
    assert main(["over_limit"]) == 1
    err = capsys.readouterr().err
    assert "DATABASE_URL" in err and "over_limit" not in err.split("DATABASE_URL")[0]


def test_cli_prints_the_run_id(capsys):
    assert main(["allowed_refund"]) == 0
    assert "run run-" in capsys.readouterr().out.splitlines()[0]


def test_cli_creates_a_ticket_and_watches_it_resolved(capsys):
    assert main(["--new-ticket", "The mug arrived chipped. Please refund $25.", "--customer", "C-1",
                 "--order", "O-1001"]) == 0
    out = capsys.readouterr().out
    assert "Ticket T-1006: open -> resolved" in out and "Refunded $25 and emailed the customer." in out
    assert "issue_refund" in out


def test_cli_new_ticket_needs_a_valid_customer(capsys):
    assert main(["--new-ticket", "x", "--customer", "C-0"]) == 2
    assert "no such customer" in capsys.readouterr().err
    assert main(["--new-ticket", "x"]) == 2
