"""The shapes of ticket requests and responses. FastAPI uses them to check input and to draw /docs."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TicketIn(BaseModel):
    """A customer writing in."""
    customer_id: str
    body: str
    order_id: str = ""


class Ticket(BaseModel):
    ticket_id: str
    customer_id: str
    order_id: str | None
    body: str
    status: str          # open, resolved or escalated
    note: str


class RunResultOut(BaseModel):
    """What happened when the agent worked on a ticket."""
    ticket_id: str
    answer: str                        # what the agent told the customer
    ticket: Ticket | None              # the ticket afterwards
    actions: list[dict[str, Any]]      # the action log: what really ran
    created_tickets: list[Ticket]      # tickets the agent opened
    transcript: list[dict[str, Any]]   # every message, in order
