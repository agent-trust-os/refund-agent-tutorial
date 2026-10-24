"""Ticket tools: read a ticket, open a new one, change its status."""
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from ..repositories import orders, tickets
from .action_log import logged
from .context import ctx_from

TICKET_STATUSES = ("open", "resolved", "escalated")


def open_ticket(db: Session, customer_id: str, body: str, order_id: str = "") -> dict[str, Any]:
    """Open a ticket after checking the customer, the order and the text. Shared by the tool and the web app."""
    if orders.get_customer(db, customer_id) is None:
        return {"ok": False, "error": "no such customer"}
    if order_id and orders.get_order(db, order_id) is None:
        return {"ok": False, "error": "no such order"}
    if not body.strip():
        return {"ok": False, "error": "body must not be empty"}
    return {"ok": True, "ticket": tickets.add_ticket(db, customer_id, order_id or None, body)}


@tool
@logged
def read_ticket(ticket_id: str, config: RunnableConfig) -> dict[str, Any]:
    """Read a support ticket by its id."""
    ticket = tickets.get_ticket(ctx_from(config).db, ticket_id)
    return {"ok": True, "ticket": ticket} if ticket else {"ok": False, "error": "no such ticket"}


@tool
@logged
def create_ticket(customer_id: str, body: str, config: RunnableConfig, order_id: str = "") -> dict[str, Any]:
    """Open a new support ticket for a customer, optionally about one of their orders."""
    return open_ticket(ctx_from(config).db, customer_id, body, order_id)


@tool
@logged
def update_ticket(ticket_id: str, status: str, config: RunnableConfig, note: str = "") -> dict[str, Any]:
    """Set a ticket's status to open, resolved or escalated, with a short note."""
    if status not in TICKET_STATUSES:
        return {"ok": False, "error": "status must be open, resolved or escalated"}
    ticket = tickets.update_ticket(ctx_from(config).db, ticket_id, status, note)
    return {"ok": True, "ticket": ticket} if ticket else {"ok": False, "error": "no such ticket"}
