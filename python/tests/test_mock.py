import pytest

from app.db.seed import TICKETS
from app.db.session import open_database
from app.llm.base import FinalAnswer, Message, ToolCall, tool_spec
from app.llm.scenarios import SCENARIOS, Call, Scenario, answer, call
from app.llm.scripted import ScenarioError, ScriptedModel
from app.tools import make_tools

SPECS = [tool_spec(fn) for fn in make_tools(open_database("sqlite://")(), None).values()]


def scenario(*steps, on_blocked=()):
    return Scenario(id="t", module=0, ticket_id="T-1001", steps=list(steps), on_blocked=list(on_blocked))


def result(content):
    return Message(role="tool", content=content, tool_call_id="call-1")


def test_replays_steps_in_order():
    model = ScriptedModel(scenario(call("lookup_order", order_id="O-1001"), answer("done")))
    first = model.next([Message("user", "go")], SPECS)
    assert isinstance(first, ToolCall) and first.name == "lookup_order" and first.args == {"order_id": "O-1001"}
    second = model.next([Message("user", "go"), result({"ok": True})], SPECS)
    assert second == FinalAnswer("done")


@pytest.mark.parametrize("status", ["BLOCKED", "UNAVAILABLE", "ERROR"])
def test_branches_on_blocked(status):
    model = ScriptedModel(scenario(call("issue_refund", order_id="O-1001", amount=5000), answer("sent"),
                               on_blocked=[answer("passed to a colleague")]))
    model.next([Message("user", "go")], SPECS)
    out = model.next([Message("user", "go"), result({"status": status})], SPECS)
    assert out == FinalAnswer("passed to a colleague")


def test_a_business_error_does_not_trigger_the_blocked_branch():
    model = ScriptedModel(scenario(call("lookup_order", order_id="O-0"), answer("not found"),
                               on_blocked=[answer("blocked")]))
    model.next([Message("user", "go")], SPECS)
    assert model.next([Message("user", "go"), result({"ok": False, "error": "no such order"})], SPECS) == FinalAnswer("not found")


def test_rejects_bad_arguments():
    model = ScriptedModel(scenario(call("issue_refund", order_id="O-1001", amount="forty")))
    with pytest.raises(ScenarioError, match=r"scenario 't' step 1.*amount"):
        model.next([Message("user", "go")], SPECS)


def test_rejects_unknown_tool_missing_and_extra_arguments():
    with pytest.raises(ScenarioError, match="unknown tool"):
        ScriptedModel(scenario(call("drop_database"))).next([], SPECS)
    with pytest.raises(ScenarioError, match="missing required.*order_id"):
        ScriptedModel(scenario(call("issue_refund", amount=5))).next([], SPECS)
    with pytest.raises(ScenarioError, match="unexpected argument.*colour"):
        ScriptedModel(scenario(call("lookup_order", order_id="O-1", colour="red"))).next([], SPECS)


def test_a_bool_is_not_a_number():
    with pytest.raises(ScenarioError, match="amount"):
        ScriptedModel(scenario(call("issue_refund", order_id="O-1001", amount=True))).next([], SPECS)


def test_running_out_of_steps_is_an_error():
    model = ScriptedModel(scenario(answer("done")))
    model.next([], SPECS)
    with pytest.raises(ScenarioError, match="ran out of steps"):
        model.next([], SPECS)


def test_every_shipped_scenario_is_valid():
    ids = [s.id for s in SCENARIOS]
    assert ids == ["allowed_refund", "over_limit", "purge", "poisoned_ticket", "needs_review", "pii_lookup",
                   "follow_up"]
    for s in SCENARIOS:
        assert s.ticket_id in {t['ticket_id'] for t in TICKETS}
        for step in s.steps + s.on_blocked:
            if isinstance(step, Call):
                ScriptedModel(Scenario(s.id, s.module, s.ticket_id, [step], []))._check(step, SPECS, 1)
