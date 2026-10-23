"""The fake shop. Its ``actions`` log is the proof of what really ran, independent of what the
agent, the model or AgentTrust says happened. Every method writes to the log before it acts."""
from __future__ import annotations

import copy
from typing import Any

from .fixtures import CUSTOMERS, ORDERS, TICKETS


class Shop:
    def __init__(self) -> None:
        self.tickets = copy.deepcopy(TICKETS)
        self.orders = copy.deepcopy(ORDERS)
        self.customers = copy.deepcopy(CUSTOMERS)
        self.actions: list[dict[str, Any]] = []
        self.refunds: list[dict[str, Any]] = []
        self.outbox: list[dict[str, Any]] = []
        self._refund_keys: dict[tuple[str, str, float], str] = {}

    def _log(self, tool: str, args: dict[str, Any]) -> None:
        self.actions.append({"seq": len(self.actions) + 1, "tool": tool, "args": dict(args)})

    def count(self, tool: str) -> int:
        return sum(1 for a in self.actions if a["tool"] == tool)

    def read_ticket(self, ticket_id: str) -> dict[str, Any]:
        self._log("read_ticket", {"ticket_id": ticket_id})
        ticket = self.tickets.get(ticket_id)
        return {"ok": True, "ticket": dict(ticket)} if ticket else {"ok": False, "error": "no such ticket"}

    def lookup_order(self, order_id: str) -> dict[str, Any]:
        self._log("lookup_order", {"order_id": order_id})
        order = self.orders.get(order_id)
        return {"ok": True, "order": dict(order)} if order else {"ok": False, "error": "no such order"}

    def lookup_customer(self, customer_id: str) -> dict[str, Any]:
        self._log("lookup_customer", {"customer_id": customer_id})
        customer = self.customers.get(customer_id)
        return {"ok": True, "customer": dict(customer)} if customer else {"ok": False, "error": "no such customer"}

    def issue_refund(self, order_id: str, amount: float, currency: str, reason: str, run_id: str) -> dict[str, Any]:
        self._log("issue_refund", {"order_id": order_id, "amount": amount, "currency": currency, "reason": reason})
        if order_id not in self.orders:
            return {"ok": False, "error": "no such order"}
        key = (run_id, order_id, float(amount))
        if key in self._refund_keys:
            return {"ok": True, "status": "duplicate", "refund_id": self._refund_keys[key]}
        refund = {"refund_id": f"R-{len(self.refunds) + 1:04d}", "order_id": order_id, "amount": amount,
                  "currency": currency, "status": "sent"}
        self.refunds.append(refund)
        self._refund_keys[key] = refund["refund_id"]
        return {"ok": True, "refund": dict(refund)}

    def send_email(self, to: str, subject: str, body: str) -> dict[str, Any]:
        self._log("send_email", {"to": to, "subject": subject, "body": body})
        message_id = f"M-{len(self.outbox) + 1:04d}"
        self.outbox.append({"message_id": message_id, "to": to, "subject": subject, "body": body})
        return {"ok": True, "message_id": message_id}

    def purge_orders(self) -> dict[str, Any]:
        self._log("purge_orders", {})
        purged = len(self.orders)
        self.orders.clear()
        return {"ok": True, "purged": purged}
