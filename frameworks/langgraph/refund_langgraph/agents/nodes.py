"""The two nodes of the graph, and the choice after the model.

``call_model`` asks the model what to do. ``run_tools`` runs the tool it named (one at a time, so a database
session is never used from two threads) and gives back the result. ``route`` decides: run a tool, or stop.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END

from ..llm.chat import parse_result
from ..tools import TOOLS_BY_NAME
from .prompts import SYSTEM_PROMPT
from .state import AgentState

log = logging.getLogger("refund_bot.agent")


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


def make_call_model(model: BaseChatModel):
    """The model node. ``model`` already knows the tools (``bind_tools``)."""

    def call_model(state: AgentState) -> dict[str, Any]:
        reply = model.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
        return {"messages": [reply], "steps": state["steps"] + 1}

    return call_model


def run_tools(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Run each tool call in the last message and answer with one ToolMessage per call."""
    ticket_id = config["configurable"].get("ticket_id")
    results: list[ToolMessage] = []
    for call in state["messages"][-1].tool_calls:
        tool = TOOLS_BY_NAME.get(call["name"])
        if tool is None:
            reply = ToolMessage(json.dumps({"status": "ERROR", "tool": call["name"],
                                            "reason": f"unknown tool {call['name']!r}"}), tool_call_id=call["id"])
        else:
            reply = tool.invoke(call, config)
        log.info("%s | call  | %s %s -> %s", ticket_id, call["name"], json.dumps(call["args"]),
                 summary(parse_result(reply.content)))
        log.debug("%s | result | %s", ticket_id, reply.content)
        results.append(reply)
    return {"messages": results}


def make_route(max_steps: int):
    def route(state: AgentState) -> str:
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls and state["steps"] < max_steps:
            return "tools"
        return END

    return route
