"""Reading orders and customers, and deleting orders."""
from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db.models import Customer, Order


def get_order(db: Session, order_id: str) -> dict[str, Any] | None:
    order = db.get(Order, order_id)
    return order.to_dict() if order else None


def list_orders(db: Session) -> list[dict[str, Any]]:
    return [o.to_dict() for o in db.scalars(select(Order).order_by(Order.order_id))]


def delete_all_orders(db: Session) -> int:
    deleted = db.execute(delete(Order)).rowcount
    db.commit()
    return deleted


def get_customer(db: Session, customer_id: str) -> dict[str, Any] | None:
    customer = db.get(Customer, customer_id)
    return customer.to_dict() if customer else None


def list_customers(db: Session) -> list[dict[str, Any]]:
    return [c.to_dict() for c in db.scalars(select(Customer).order_by(Customer.customer_id))]
