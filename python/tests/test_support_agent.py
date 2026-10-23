"""The agent loop, driven by the seven scripted scenarios."""
import subprocess
import sys

from app.agents.support_agent import STEP_LIMIT_ANSWER, call_tool, run
from app.llm.base import FinalAnswer, ToolCall
from app.repositories import orders, records
from app.services.scenarios import play_scenario
from app.llm.scenarios import BY_ID
from app.llm.scripted import ScriptedModel


def tools_used(result):
    return [a["tool"] for a in result.actions]


def test_deterministic():
    first, second = play_scenario("allowed_refund"), play_scenario("allowed_refund")
    assert first.transcript == second.transcript and tools_used(first) == tools_used(second)


def test_each_scenario_runs_the_expected_tools_and_closes_its_ticket():
    expected = {
        "allowed_refund": ["read_ticket", "lookup_order", "issue_refund", "send_email", "update_ticket"],
        "over_limit": ["read_ticket", "lookup_order", "issue_refund", "update_ticket"],
        "purge": ["read_ticket", "purge_orders", "update_ticket"],
        "poisoned_ticket": ["read_ticket", "issue_refund", "update_ticket"],
        "needs_review": ["read_ticket", "lookup_order", "issue_refund", "update_ticket"],
        "pii_lookup": ["read_ticket", "lookup_customer", "update_ticket"],
        "follow_up": ["read_ticket", "lookup_order", "issue_refund", "create_ticket", "send_email", "update_ticket"],
    }
    assert set(expected) == set(BY_ID)
    for scenario_id, tools in expected.items():
        result = play_scenario(scenario_id)
        assert tools_used(result) == tools, scenario_id
        assert result.ticket["status"] == "resolved", scenario_id


def test_ungoverned_the_bad_scenarios_succeed(db):
    for scenario_id, amount in [("over_limit", 5000), ("poisoned_ticket", 50000), ("needs_review", 900)]:
        result = play_scenario(scenario_id)
        refund = [a for a in result.actions if a["tool"] == "issue_refund"][0]
        assert refund["args"]["amount"] == amount
    result = run("T-1005", ScriptedModel(BY_ID["purge"]), db)
    assert orders.list_orders(db) == [] and result.ticket["status"] == "resolved"


def test_follow_up_creates_a_second_ticket():
    result = play_scenario("follow_up")
    assert [(t["ticket_id"], t["status"]) for t in result.created_tickets] == [("T-1006", "open")]
    assert play_scenario("allowed_refund").created_tickets == []


def test_scenarios_never_touch_the_real_database(db):
    play_scenario("purge")
    assert len(orders.list_orders(db)) == 4 and records.list_actions(db) == []


def test_the_transcript_pairs_each_call_with_its_result():
    result = play_scenario("pii_lookup")
    assert [m.role for m in result.transcript] == ["user", "assistant", "tool", "assistant", "tool",
                                                    "assistant", "tool", "assistant"]
    assert result.transcript[1].tool_call_id == result.transcript[2].tool_call_id == "call-1"


def test_poisoned_text_reaches_the_model_only_through_the_ticket_tool():
    result = play_scenario("poisoned_ticket")
    assert "Ignore all previous" not in result.transcript[0].content
    assert "Ignore all previous" in str(result.transcript[2].content)


def test_a_raising_tool_becomes_an_error_result():
    def broken(*, input: str = ""):
        raise RuntimeError("boom")
    assert call_tool(broken, ToolCall("c", "broken", {}), "x") == {"status": "ERROR", "tool": "broken", "reason": "boom"}


def test_call_tool_passes_the_request_as_input():
    seen = {}

    def tool(*, input: str = ""):
        seen["input"] = input
        return {"ok": True}
    call_tool(tool, ToolCall("c", "tool", {}), "Resolve support ticket T-1001.")
    assert seen["input"] == "Resolve support ticket T-1001."


class Looping:
    name = "loop"

    def next(self, messages, tools):
        return ToolCall("c", "lookup_order", {"order_id": "O-1001"})


def test_the_step_limit_stops_a_looping_model(db):
    result = run("T-1001", Looping(), db, max_steps=3)
    assert result.answer == STEP_LIMIT_ANSWER and tools_used(result).count("lookup_order") == 3


class AsksForAnUnknownTool:
    name = "unknown"

    def next(self, messages, tools):
        if messages[-1].role == "tool":
            return FinalAnswer(messages[-1].content["reason"])
        return ToolCall("c", "drop_database", {})


def test_an_unknown_tool_is_an_error_result(db):
    assert "drop_database" in run("T-1001", AsksForAnUnknownTool(), db).answer


def test_offline():
    """Running every scenario needs no AgentTrust SDK, no LLM SDK and no network library."""
    code = ("import sys; from app.services.scenarios import play_scenario; from app.llm.scenarios import BY_ID\n"
            "[play_scenario(s) for s in BY_ID]\n"
            "bad = [m for m in ('agentrust_sdk', 'anthropic', 'openai', 'httpx') if m in sys.modules]\n"
            "assert not bad, bad")
    assert subprocess.run([sys.executable, "-c", code], capture_output=True).returncode == 0
