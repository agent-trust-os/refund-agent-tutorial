"""The database tables. One shared database, like a real helpdesk.

customers ─┬─ orders
           └─ tickets ── refunds, emails, actions (each linked to the ticket being worked on)

``actions`` is the action log: one row per tool call, written before the tool runs. It is the proof of
what the agent really did, whatever the agent says.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Money(TypeDecorator):
    """Stored as numeric(12,2); always read back as a plain float, on SQLite and Postgres alike."""
    impl = Numeric(12, 2)
    cache_ok = True

    def process_result_value(self, value, dialect):
        return None if value is None else float(value)


class Base(DeclarativeBase):
    def to_dict(self) -> dict[str, Any]:
        return {c.name: getattr(self, c.key) for c in self.__table__.columns}


class Customer(Base):
    __tablename__ = "customers"
    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)
    ssn: Mapped[str] = mapped_column(String)
    card_number: Mapped[str] = mapped_column(String)


class Order(Base):
    __tablename__ = "orders"
    order_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String)
    total: Mapped[float] = mapped_column(Money())
    currency: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    delivered_late: Mapped[bool] = mapped_column(Boolean)


class Ticket(Base):
    __tablename__ = "tickets"
    ticket_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String)
    order_id: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, default="open")      # open, resolved or escalated
    note: Mapped[str] = mapped_column(Text, default="")


class Refund(Base):
    __tablename__ = "refunds"
    # The same refund for the same ticket is paid once: a retried call finds the first one.
    __table_args__ = (UniqueConstraint("ticket_id", "order_id", "amount"),)
    refund_id: Mapped[str] = mapped_column(String, primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String)
    order_id: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Money())
    currency: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Email(Base):
    __tablename__ = "emails"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str | None] = mapped_column(String, nullable=True)
    to: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Action(Base):
    __tablename__ = "actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str | None] = mapped_column(String, nullable=True)
    tool: Mapped[str] = mapped_column(String)
    # JSON, not JSONB, on Postgres: the arguments keep the order the tool received them in.
    args: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
