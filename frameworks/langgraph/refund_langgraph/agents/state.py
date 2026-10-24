"""The graph's state, and what one run of the agent produces."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from ..llm.base import Message


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]    # the conversation: request, tool calls, results, answer
    steps: int                                             # how many times the model has been asked


@dataclass
class RunResult:
    ticket_id: str
    transcript: list[Message]                 # every message: the request, each tool call and result, the answer
    answer: str                               # what the agent told the customer
    ticket: dict[str, Any] | None             # the ticket after the run: its status and note
    actions: list[dict[str, Any]]             # the action log for this ticket: what really ran
    created_tickets: list[dict[str, Any]] = field(default_factory=list)   # tickets the agent opened
