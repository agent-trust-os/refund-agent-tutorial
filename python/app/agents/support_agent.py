"""The agent loop: ask the model what to do, run the tool it names, give it the result, repeat.

The loop knows nothing about refunds or tickets. It only moves messages between the model and the tools,
so the model can be swapped (scripted, rule-based, later a real LLM) and the tools can be wrapped
(later by AgentTrust) without changing this file.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from sqlalchemy.orm import Session

from ..llm.base import FinalAnswer, Message, Model, ToolCall, tool_spec
from ..repositories import records, tickets
from ..tools import make_tools
from .prompts import ticket_request
from .state import RunResult

STEP_LIMIT_ANSWER = "Stopped: step limit reached"

log = logging.getLogger("refund_bot.agent")


def call_tool(fn: Callable[..., dict[str, Any]], call: ToolCall, request: str) -> dict[str, Any]:
    """Run one tool call. The request goes in as the hidden ``input`` argument. A tool that raises
    becomes an ERROR result, so the model can recover instead of the loop crashing."""
    try:
        return fn(**call.args, input=request)
    except Exception as exc:
        return {"status": "ERROR", "tool": call.name, "reason": str(exc)}


def summary(result: dict[str, Any]) -> str:
    """One short word for a tool result, for the log: ok, duplicate, an error, or BLOCKED and why."""
    if result.get("status") in ("ERROR", "BLOCKED", "UNAVAILABLE"):
        return f"{result['status']}: {result.get('reason', '')}"
    if result.get("ok") is False:
        return f"error: {result['error']}"
    if result.get("status") == "duplicate":
        return f"duplicate of {result['refund_id']}"
    for key, label in (("refund", "refund_id"), ("ticket", "ticket_id")):
        if key in result:
            item = result[key]
            return f"ok {item[label]}" + (f" ({item['status']})" if key == "ticket" else "")
    return "ok"


def run(ticket_id: str, model: Model, db: Session, max_steps: int = 10, governed: str | None = None) -> RunResult:
    """Work on one ticket until the model gives its final answer.

    ``max_steps`` is a local safety net so a looping model cannot run forever. It is not a governance control.
    ``governed`` says how AgentTrust guards the tools: None (not at all), "harness" or "client".
    """
    tools = make_tools(db, ticket_id, governed)
    specs = [tool_spec(fn) for fn in tools.values()]
    before = {t["ticket_id"] for t in tickets.list_tickets(db)}
    request = ticket_request(ticket_id)
    messages = [Message("user", request)]
    answer = STEP_LIMIT_ANSWER
    log.info("%s | start | model=%s", ticket_id, getattr(model, "name", type(model).__name__))

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
        log.info("%s | call  | %s %s -> %s", ticket_id, step.name, json.dumps(step.args), summary(result))
        log.debug("%s | result | %s", ticket_id, json.dumps(result))
        messages.append(Message("tool", result, tool_call_id=step.id))

    # TODO(AgentTrust 10/11): check the final answer with validate before returning it. Paste from docs/guides/direct-api.html#todo-10
    ticket = tickets.get_ticket(db, ticket_id)
    log.info("%s | done  | ticket %s | answer: %s", ticket_id, ticket["status"] if ticket else "missing", answer)
    return RunResult(
        ticket_id=ticket_id,
        transcript=messages,
        answer=answer,
        ticket=ticket,
        actions=records.list_actions(db, ticket_id=ticket_id),
        created_tickets=[t for t in tickets.list_tickets(db) if t["ticket_id"] not in before],
    )
