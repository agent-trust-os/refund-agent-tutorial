"""Tickets: list them, submit one, read one, and let the agent resolve one."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...agents.state import RunResult
from ...db.session import get_db
from ...repositories import tickets
from ...schemas.tickets import RunResultOut, Ticket, TicketIn
from ...services.tickets import TicketError, resolve_ticket, submit_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])


def result_out(result: RunResult) -> RunResultOut:
    return RunResultOut(ticket_id=result.ticket_id, answer=result.answer, ticket=result.ticket,
                        actions=result.actions, created_tickets=result.created_tickets,
                        transcript=[asdict(m) for m in result.transcript])


@router.get("", response_model=list[Ticket])
def list_tickets(status: str | None = None, db: Session = Depends(get_db)):
    """All tickets, or only those with this status (open, resolved, escalated)."""
    return tickets.list_tickets(db, status)


@router.post("", response_model=Ticket, status_code=201)
def create(ticket: TicketIn, db: Session = Depends(get_db)):
    """A customer writes in. The ticket starts open."""
    return submit_ticket(db, ticket.customer_id, ticket.body, ticket.order_id)


@router.get("/{ticket_id}", response_model=Ticket)
def read(ticket_id: str, db: Session = Depends(get_db)):
    ticket = tickets.get_ticket(db, ticket_id)
    if ticket is None:
        raise TicketError(f"no such ticket {ticket_id!r}", 404)
    return ticket


@router.post("/{ticket_id}/resolve", response_model=RunResultOut)
def resolve(ticket_id: str, db: Session = Depends(get_db)):
    """The agent works on an open ticket and answers with everything it did."""
    return result_out(resolve_ticket(db, ticket_id))
