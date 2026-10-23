"""The agent loop: ask the model what to do, run the tool it names, give it the result, repeat.

The loop knows nothing about refunds or tickets. It only moves messages between the model and the tools,
so the model can be swapped (scripted, rule-based, later a real LLM) and the tools can be wrapped
(later by AgentTrust) without changing this file.
"""
from __future__ import annotations

from typing import Any, Callable

from sqlalchemy.orm import Session

from ..llm.base import FinalAnswer, Message, Model, ToolCall, tool_spec
from ..repositories import records, tickets
from ..tools import make_tools
from .prompts import ticket_request
from .state import RunResult

STEP_LIMIT_ANSWER = "Stopped: step limit reached"


def call_tool(fn: Callable[..., dict[str, Any]], call: ToolCall, request: str) -> dict[str, Any]:
    """Run one tool call. The request goes in as the hidden ``input`` argument. A tool that raises
    becomes an ERROR result, so the model can recover instead of the loop crashing."""
    try:
        return fn(**call.args, input=request)
    except Exception as exc:
        return {"status": "ERROR", "tool": call.name, "reason": str(exc)}


def run(ticket_id: str, model: Model, db: Session, max_steps: int = 10) -> RunResult:
    """Work on one ticket until the model gives its final answer.

    ``max_steps`` is a local safety net so a looping model cannot run forever. It is not a governance control.
    """
    tools = make_tools(db, ticket_id)
    specs = [tool_spec(fn) for fn in tools.values()]
    before = {t["ticket_id"] for t in tickets.list_tickets(db)}
    request = ticket_request(ticket_id)
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

    return RunResult(
        ticket_id=ticket_id,
        transcript=messages,
        answer=answer,
        ticket=tickets.get_ticket(db, ticket_id),
        actions=records.list_actions(db, ticket_id=ticket_id),
        created_tickets=[t for t in tickets.list_tickets(db) if t["ticket_id"] not in before],
    )
