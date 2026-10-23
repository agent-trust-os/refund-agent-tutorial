"""Look at the shop: orders, customers, refunds, emails and the action log. And put it back to the start."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...db.seed import reset_database
from ...db.session import get_db
from ...repositories import orders, records
from ...schemas.data import Action, Customer, Email, Order, Refund

router = APIRouter(tags=["data"])


@router.get("/orders", response_model=list[Order])
def list_orders(db: Session = Depends(get_db)):
    return orders.list_orders(db)


@router.get("/customers", response_model=list[Customer])
def list_customers(db: Session = Depends(get_db)):
    return orders.list_customers(db)


@router.get("/refunds", response_model=list[Refund])
def list_refunds(db: Session = Depends(get_db)):
    return records.list_refunds(db)


@router.get("/emails", response_model=list[Email])
def list_emails(db: Session = Depends(get_db)):
    """Every email the agent sent. In Docker they are also in Mailpit at http://localhost:8025."""
    return records.list_emails(db)


@router.get("/actions", response_model=list[Action])
def list_actions(ticket_id: str | None = None, db: Session = Depends(get_db)):
    """The action log: every tool call, oldest first. Filter with ?ticket_id=T-1006."""
    return records.list_actions(db, ticket_id)


@router.post("/reset")
def reset(db: Session = Depends(get_db)) -> dict[str, str]:
    """Delete everything and put the starting data back."""
    reset_database(db)
    return {"status": "reset"}
