"""The fake shop. Its action log is the proof of what really ran, independent of what the agent,
the model or AgentTrust says happened. Every method writes to the log before it acts.

The shop owns no data itself: it reads and writes a ``Store`` (in memory by default, Postgres when
configured) for one run, and sends email through a ``Mailer``.
"""
from __future__ import annotations

import uuid
from typing import Any

from .mail import Mailer, MemoryMailer
from .store import MemoryStore, Store


TICKET_STATUSES = ("open", "resolved", "escalated")


def new_run_id() -> str:
    return f"run-{uuid.uuid4().hex[:8]}"


class Shop:
    def __init__(self, store: Store | None = None, run_id: str | None = None,
                 mailer: Mailer | None = None) -> None:
        self.store: Store = store or MemoryStore()
        self.run_id = run_id or new_run_id()
        self.mailer: Mailer = mailer or MemoryMailer()

    def __enter__(self) -> "Shop":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self.store.close()

    # What really ran, for tests and for the command line.
    @property
    def actions(self) -> list[dict[str, Any]]:
        return self.store.actions()

    @property
    def tickets(self) -> dict[str, dict[str, Any]]:
        return self.store.tickets()

    @property
    def refunds(self) -> list[dict[str, Any]]:
        return self.store.refunds()

    @property
    def orders(self) -> dict[str, dict[str, Any]]:
        return self.store.orders()

    @property
    def outbox(self) -> list[dict[str, Any]]:
        """Messages held in memory; empty when the mailer is SMTP (look in Mailpit instead)."""
        return getattr(self.mailer, "outbox", [])

    def count(self, tool: str) -> int:
        return sum(1 for a in self.actions if a["tool"] == tool)

    def read_ticket(self, ticket_id: str) -> dict[str, Any]:
        self.store.log_action("read_ticket", {"ticket_id": ticket_id})
        ticket = self.store.get_ticket(ticket_id)
        return {"ok": True, "ticket": ticket} if ticket else {"ok": False, "error": "no such ticket"}

    def lookup_order(self, order_id: str) -> dict[str, Any]:
        self.store.log_action("lookup_order", {"order_id": order_id})
        order = self.store.get_order(order_id)
        return {"ok": True, "order": order} if order else {"ok": False, "error": "no such order"}

    def lookup_customer(self, customer_id: str) -> dict[str, Any]:
        self.store.log_action("lookup_customer", {"customer_id": customer_id})
        customer = self.store.get_customer(customer_id)
        return {"ok": True, "customer": customer} if customer else {"ok": False, "error": "no such customer"}

    def issue_refund(self, order_id: str, amount: float, currency: str, reason: str) -> dict[str, Any]:
        self.store.log_action("issue_refund", {"order_id": order_id, "amount": amount, "currency": currency,
                                               "reason": reason})
        if self.store.get_order(order_id) is None:
            return {"ok": False, "error": "no such order"}
        existing = self.store.find_refund(order_id, amount)
        if existing:
            return {"ok": True, "status": "duplicate", "refund_id": existing}
        return {"ok": True, "refund": self.store.add_refund(order_id, amount, currency, reason)}

    def send_email(self, to: str, subject: str, body: str) -> dict[str, Any]:
        self.store.log_action("send_email", {"to": to, "subject": subject, "body": body})
        return {"ok": True, "message_id": self.mailer.send(to, subject, body)}

    def create_ticket(self, customer_id: str, body: str, order_id: str = "") -> dict[str, Any]:
        """Open a ticket as an agent action (logged like every tool call)."""
        self.store.log_action("create_ticket", {"customer_id": customer_id, "body": body, "order_id": order_id})
        return self.submit_ticket(customer_id, body, order_id)

    def submit_ticket(self, customer_id: str, body: str, order_id: str = "") -> dict[str, Any]:
        """Open a ticket from outside the agent (a customer writing in). Not an agent action, so not logged."""
        if self.store.get_customer(customer_id) is None:
            return {"ok": False, "error": "no such customer"}
        if order_id and self.store.get_order(order_id) is None:
            return {"ok": False, "error": "no such order"}
        if not body.strip():
            return {"ok": False, "error": "body must not be empty"}
        return {"ok": True, "ticket": self.store.add_ticket(customer_id, order_id or None, body)}

    def update_ticket(self, ticket_id: str, status: str, note: str) -> dict[str, Any]:
        self.store.log_action("update_ticket", {"ticket_id": ticket_id, "status": status, "note": note})
        if status not in TICKET_STATUSES:
            return {"ok": False, "error": "status must be open, resolved or escalated"}
        ticket = self.store.update_ticket(ticket_id, status, note)
        return {"ok": True, "ticket": ticket} if ticket else {"ok": False, "error": "no such ticket"}

    def purge_orders(self) -> dict[str, Any]:
        self.store.log_action("purge_orders", {})
        return {"ok": True, "purged": self.store.purge_orders()}
