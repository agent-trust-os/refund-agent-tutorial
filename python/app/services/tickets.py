"""The ticket workflow, shared by the command line and the API.

1. ``submit_ticket``: a customer writes in. This is not an agent action, so it is not in the action log.
2. ``resolve_ticket``: the agent works on an open ticket with the rule-based mock LLM.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from ..agents.state import RunResult
from ..agents.support_agent import run
from ..llm.rules import RuleModel
from ..repositories import tickets
from ..tools.context import ToolContext
from ..tools.tickets import create_ticket

log = logging.getLogger("refund_bot.tickets")


class TicketError(Exception):
    """A request about a ticket that cannot be carried out. ``status`` is the HTTP status to answer with."""

    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.message, self.status = message, status


def submit_ticket(db: Session, customer_id: str, body: str, order_id: str = "") -> dict[str, Any]:
    """Open a ticket for a customer. Raises TicketError (400) for an unknown customer or order, or an empty body."""
    result = create_ticket(ToolContext(db, None), customer_id, body, order_id)
    if not result["ok"]:
        raise TicketError(result["error"], 400)
    ticket = result["ticket"]
    log.info("%s | submitted | customer %s, order %s: %s", ticket["ticket_id"], customer_id, order_id or "-", body)
    return ticket


def resolve_ticket(db: Session, ticket_id: str) -> RunResult:
    """Let the agent work on an open ticket. Raises TicketError: 404 if unknown, 409 if not open."""
    ticket = tickets.get_ticket(db, ticket_id)
    if ticket is None:
        raise TicketError(f"no such ticket {ticket_id!r}", 404)
    if ticket["status"] != "open":
        raise TicketError(f"ticket {ticket_id} is already {ticket['status']}", 409)
    # TODO(AgentTrust 6/11): add a governed= parameter and pass it to run. Paste from docs/guides/harness.html#todo-6
    return run(ticket_id, RuleModel(), db)
