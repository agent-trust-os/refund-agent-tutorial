"""Reading and writing tickets. Every function takes the database session first and returns plain dicts."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Ticket


def get_ticket(db: Session, ticket_id: str) -> dict[str, Any] | None:
    ticket = db.get(Ticket, ticket_id)
    return ticket.to_dict() if ticket else None


def list_tickets(db: Session, status: str | None = None) -> list[dict[str, Any]]:
    query = select(Ticket).order_by(Ticket.ticket_id)
    if status:
        query = query.where(Ticket.status == status)
    return [t.to_dict() for t in db.scalars(query)]


def next_ticket_id(db: Session) -> str:
    """T-1001, T-1002, ... : one more than the highest number used so far."""
    numbers = [int(t.split("-")[1]) for t in db.scalars(select(Ticket.ticket_id))]
    return f"T-{max(numbers, default=1000) + 1}"


def add_ticket(db: Session, customer_id: str, order_id: str | None, body: str) -> dict[str, Any]:
    ticket = Ticket(ticket_id=next_ticket_id(db), customer_id=customer_id, order_id=order_id, body=body,
                    status="open", note="")
    db.add(ticket)
    db.commit()
    return ticket.to_dict()


def update_ticket(db: Session, ticket_id: str, status: str, note: str) -> dict[str, Any] | None:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        return None
    ticket.status, ticket.note = status, note
    db.commit()
    return ticket.to_dict()
