"""The shapes of the read-only lists: orders, customers, refunds, emails, the action log and scenarios."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Order(BaseModel):
    order_id: str
    customer_id: str
    total: float
    currency: str
    status: str
    delivered_late: bool


class Customer(BaseModel):
    customer_id: str
    name: str
    email: str
    ssn: str
    card_number: str


class Refund(BaseModel):
    refund_id: str
    ticket_id: str
    order_id: str
    amount: float
    currency: str
    reason: str
    status: str


class Email(BaseModel):
    id: int
    ticket_id: str | None
    to: str
    subject: str
    body: str


class Action(BaseModel):
    id: int
    ticket_id: str | None
    tool: str
    args: dict[str, Any]


class ScenarioInfo(BaseModel):
    id: str
    ticket_id: str
