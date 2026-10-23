"""The agent loop: ask the model for a step, run the tool it names, hand the result back."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from refund_core.models.base import FinalAnswer, Message, Model, ToolCall, tool_spec
from refund_core.scenarios import Scenario
from refund_core.shop import Shop
from refund_core.tools import make_tools

STEP_LIMIT_ANSWER = "Stopped: step limit reached"


@dataclass
class RunResult:
    transcript: list[Message]
    answer: str
    actions: list[dict[str, Any]]


def call_tool(fn: Callable[..., dict[str, Any]], call: ToolCall, request: str) -> dict[str, Any]:
    """Run one tool call. The request text goes in as the hidden ``input`` argument; a tool that
    raises becomes an ERROR result so the model can recover instead of the loop crashing."""
    try:
        return fn(**call.args, input=request)
    except Exception as exc:
        return {"status": "ERROR", "tool": call.name, "reason": str(exc)}


def run(scenario: Scenario, model: Model, shop: Shop, max_steps: int = 10) -> RunResult:
    """``max_steps`` is a local safety net so a looping model cannot run forever. It is not a
    governance control."""
    tools = make_tools(shop, run_id=scenario.id)
    specs = [tool_spec(fn) for fn in tools.values()]
    request = f"Resolve support ticket {scenario.ticket_id}."
    messages = [Message("user", request)]
    answer = STEP_LIMIT_ANSWER
    for _ in range(max_steps):
        step = model.next(messages, specs)
        if isinstance(step, FinalAnswer):
            answer = step.text
            messages.append(Message("assistant", answer))
            break
        messages.append(Message("assistant", {"tool": step.name, "args": step.args}, tool_call_id=step.id))
        fn = tools.get(step.name)
        if fn is None:
            result = {"status": "ERROR", "tool": step.name, "reason": f"unknown tool {step.name!r}"}
        else:
            result = call_tool(fn, step, request)
        messages.append(Message("tool", result, tool_call_id=step.id))
    return RunResult(transcript=messages, answer=answer, actions=list(shop.actions))
