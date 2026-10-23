"""What one run of the agent produces."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..llm.base import Message


@dataclass
class RunResult:
    ticket_id: str
    transcript: list[Message]                 # every message: the request, each tool call and result, the answer
    answer: str                               # what the agent told the customer
    ticket: dict[str, Any] | None             # the ticket after the run: its status and note
    actions: list[dict[str, Any]]             # the action log for this ticket: what really ran
    created_tickets: list[dict[str, Any]] = field(default_factory=list)   # tickets the agent opened
