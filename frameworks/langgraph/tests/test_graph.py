"""The graph: its shape, how it runs each ticket and scenario, the step limit, and the model choice."""
import json

import pytest
from langchain_core.messages import ToolMessage

from refund_langgraph.agents.graph import build_graph
from refund_langgraph.agents.runner import STEP_LIMIT_ANSWER, run
from refund_langgraph.llm.chat import ModelChat
from refund_langgraph.llm.base import ToolCall
from refund_langgraph.llm.factory import ModelError, get_model
from refund_langgraph.llm.rules import RuleModel
from refund_langgraph.llm.scenarios import BY_ID, SCENARIOS
from refund_langgraph.llm.scripted import ScriptedModel
from refund_langgraph.services.scenarios import play_scenario
from refund_langgraph.tools import TOOLS_BY_NAME


def tools_of(result):
    return [m.content["tool"] for m in result.transcript if m.role == "assistant" and isinstance(m.content, dict)]


def test_the_graph_has_a_model_and_a_tools_node():
    graph = build_graph(ModelChat(brain=RuleModel())).get_graph()
    assert {"model", "tools"} <= set(graph.nodes)
    assert "model" in graph.draw_mermaid() and "tools" in graph.draw_mermaid()


@pytest.mark.parametrize("ticket_id, tools, status", [
    ("T-1001", ["read_ticket", "lookup_order", "lookup_customer", "issue_refund", "create_ticket", "send_email",
                "update_ticket"], "resolved"),
    ("T-1003", ["read_ticket", "lookup_order", "lookup_customer", "issue_refund", "send_email", "update_ticket"],
     "resolved"),
    ("T-1005", ["read_ticket", "lookup_customer", "purge_orders", "update_ticket"], "resolved"),
])
def test_the_rule_model_resolves_the_starting_tickets(db, ticket_id, tools, status):
    result = run(ticket_id, db, ModelChat(brain=RuleModel()))
    assert tools_of(result) == tools
    assert result.ticket["status"] == status
    assert [a["tool"] for a in result.actions] == tools


def test_a_failed_call_makes_the_agent_escalate(db, monkeypatch):
    def refuse(*args):
        raise RuntimeError("refund service is down")
    monkeypatch.setattr("refund_langgraph.tools.refunds.records.add_refund", refuse)
    result = run("T-1001", db, ModelChat(brain=RuleModel()))
    assert result.ticket["status"] == "escalated"
    assert "colleague" in result.answer


@pytest.mark.parametrize("scenario", [s.id for s in SCENARIOS])
def test_every_scenario_plays(scenario):
    result = play_scenario(scenario)
    steps = [s.name for s in BY_ID[scenario].steps if hasattr(s, "name")]
    assert tools_of(result) == steps
    assert result.answer


class Blocked:
    """Stands in for a governed tool: AgentTrust says no."""

    def invoke(self, call, config):
        result = {"status": "BLOCKED", "tool": call["name"], "reason": "over the limit"}
        return ToolMessage(json.dumps(result), tool_call_id=call["id"])


def test_a_blocked_result_switches_the_script_to_its_blocked_steps(db, monkeypatch):
    monkeypatch.setattr("refund_langgraph.agents.nodes.TOOLS_BY_NAME", {**TOOLS_BY_NAME, "issue_refund": Blocked()})
    result = run("T-1003", db, ModelChat(brain=ScriptedModel(BY_ID["over_limit"])))
    assert tools_of(result) == ["read_ticket", "lookup_order", "issue_refund", "update_ticket"]
    assert result.ticket["status"] == "escalated"
    assert "colleague" in result.answer


class Looping:
    name = "mock/looping"

    def __init__(self):
        self.calls = 0

    def next(self, messages, tools):
        self.calls += 1
        return ToolCall(f"call-{self.calls}", "read_ticket", {"ticket_id": "T-1001"})


def test_the_step_limit_stops_a_model_that_never_answers(db):
    result = run("T-1001", db, ModelChat(brain=Looping()), max_steps=3)
    assert result.answer == STEP_LIMIT_ANSWER
    assert len(tools_of(result)) == 3


def test_the_default_model_is_the_mock(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert isinstance(get_model(), ModelChat)


def test_auto_uses_the_mock_without_a_key(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "auto")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_model(), ModelChat)


def test_anthropic_without_a_key_is_an_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ModelError, match="ANTHROPIC_API_KEY"):
        get_model()


def test_an_unknown_provider_is_an_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "nope")
    with pytest.raises(ModelError, match="unknown LLM_PROVIDER"):
        get_model()
