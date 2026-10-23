"""Ticket tools: read a ticket, open a new one, change its status."""
from __future__ import annotations

from typing import Any

from ..repositories import orders, tickets
from .context import ToolContext

TICKET_STATUSES = ("open", "resolved", "escalated")


def read_ticket(ctx: ToolContext, ticket_id: str) -> dict[str, Any]:
    """Read a support ticket by its id."""
    ticket = tickets.get_ticket(ctx.db, ticket_id)
    return {"ok": True, "ticket": ticket} if ticket else {"ok": False, "error": "no such ticket"}


def create_ticket(ctx: ToolContext, customer_id: str, body: str, order_id: str = "") -> dict[str, Any]:
    """Open a new support ticket for a customer, optionally about one of their orders."""
    if orders.get_customer(ctx.db, customer_id) is None:
        return {"ok": False, "error": "no such customer"}
    if order_id and orders.get_order(ctx.db, order_id) is None:
        return {"ok": False, "error": "no such order"}
    if not body.strip():
        return {"ok": False, "error": "body must not be empty"}
    return {"ok": True, "ticket": tickets.add_ticket(ctx.db, customer_id, order_id or None, body)}


def update_ticket(ctx: ToolContext, ticket_id: str, status: str, note: str = "") -> dict[str, Any]:
    """Set a ticket's status to open, resolved or escalated, with a short note."""
    if status not in TICKET_STATUSES:
        return {"ok": False, "error": "status must be open, resolved or escalated"}
    ticket = tickets.update_ticket(ctx.db, ticket_id, status, note)
    return {"ok": True, "ticket": ticket} if ticket else {"ok": False, "error": "no such ticket"}
