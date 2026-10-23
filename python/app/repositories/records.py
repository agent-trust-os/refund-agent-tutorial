"""What the agent leaves behind: refunds, emails and the action log."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db.models import Action, Email, Refund

REFUND_FIELDS = ("refund_id", "ticket_id", "order_id", "amount", "currency", "reason", "status")


def _refund(refund: Refund) -> dict[str, Any]:
    return {k: getattr(refund, k) for k in REFUND_FIELDS}


def find_refund(db: Session, ticket_id: str, order_id: str, amount: float) -> str | None:
    """The id of a refund already paid for this ticket, order and amount, if there is one."""
    return db.scalar(select(Refund.refund_id).where(
        Refund.ticket_id == ticket_id, Refund.order_id == order_id, Refund.amount == amount))


def add_refund(db: Session, ticket_id: str, order_id: str, amount: float, currency: str,
               reason: str) -> dict[str, Any]:
    count = db.scalar(select(func.count()).select_from(Refund))
    refund = Refund(refund_id=f"R-{count + 1:04d}", ticket_id=ticket_id, order_id=order_id, amount=amount,
                    currency=currency, reason=reason, status="sent")
    db.add(refund)
    db.commit()
    return _refund(refund)


def list_refunds(db: Session) -> list[dict[str, Any]]:
    return [_refund(r) for r in db.scalars(select(Refund).order_by(Refund.refund_id))]


def add_email(db: Session, ticket_id: str | None, to: str, subject: str, body: str) -> dict[str, Any]:
    email = Email(ticket_id=ticket_id, to=to, subject=subject, body=body)
    db.add(email)
    db.commit()
    return {"id": email.id, "ticket_id": ticket_id, "to": to, "subject": subject, "body": body}


def list_emails(db: Session) -> list[dict[str, Any]]:
    return [{"id": e.id, "ticket_id": e.ticket_id, "to": e.to, "subject": e.subject, "body": e.body}
            for e in db.scalars(select(Email).order_by(Email.id))]


def add_action(db: Session, ticket_id: str | None, tool: str, args: dict[str, Any]) -> None:
    db.add(Action(ticket_id=ticket_id, tool=tool, args=dict(args)))
    db.commit()


def list_actions(db: Session, ticket_id: str | None = None) -> list[dict[str, Any]]:
    """The action log, oldest first, optionally for one ticket."""
    query = select(Action).order_by(Action.id)
    if ticket_id:
        query = query.where(Action.ticket_id == ticket_id)
    return [{"id": a.id, "ticket_id": a.ticket_id, "tool": a.tool, "args": a.args} for a in db.scalars(query)]
