"""Where the shop keeps its data. ``MemoryStore`` is the default (no services, used by the tests);
``PostgresStore`` in ``pgstore.py`` keeps the same data in Postgres."""
from __future__ import annotations

import copy
from typing import Any, Protocol

from .fixtures import CUSTOMERS, ORDERS, TICKETS


class Store(Protocol):
    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None: ...
    def tickets(self) -> dict[str, dict[str, Any]]: ...
    def update_ticket(self, ticket_id: str, status: str, note: str) -> dict[str, Any] | None: ...
    def get_order(self, order_id: str) -> dict[str, Any] | None: ...
    def get_customer(self, customer_id: str) -> dict[str, Any] | None: ...
    def orders(self) -> dict[str, dict[str, Any]]: ...
    def purge_orders(self) -> int: ...
    def find_refund(self, order_id: str, amount: float) -> str | None:
        """The refund id already stored for this order and amount in this run, if any."""
    def add_refund(self, order_id: str, amount: float, currency: str, reason: str) -> dict[str, Any]: ...
    def refunds(self) -> list[dict[str, Any]]: ...
    def log_action(self, tool: str, args: dict[str, Any]) -> None: ...
    def actions(self) -> list[dict[str, Any]]: ...
    def close(self) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self._tickets = copy.deepcopy(TICKETS)
        self._orders = copy.deepcopy(ORDERS)
        self._customers = copy.deepcopy(CUSTOMERS)
        self._refunds: list[dict[str, Any]] = []
        self._refund_keys: dict[tuple[str, float], str] = {}
        self._actions: list[dict[str, Any]] = []

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        ticket = self._tickets.get(ticket_id)
        return dict(ticket) if ticket else None

    def tickets(self) -> dict[str, dict[str, Any]]:
        return {k: dict(v) for k, v in self._tickets.items()}

    def update_ticket(self, ticket_id: str, status: str, note: str) -> dict[str, Any] | None:
        ticket = self._tickets.get(ticket_id)
        if ticket is None:
            return None
        ticket["status"], ticket["note"] = status, note
        return dict(ticket)

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        order = self._orders.get(order_id)
        return dict(order) if order else None

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        customer = self._customers.get(customer_id)
        return dict(customer) if customer else None

    def orders(self) -> dict[str, dict[str, Any]]:
        return {k: dict(v) for k, v in self._orders.items()}

    def purge_orders(self) -> int:
        purged = len(self._orders)
        self._orders.clear()
        return purged

    def find_refund(self, order_id: str, amount: float) -> str | None:
        return self._refund_keys.get((order_id, float(amount)))

    def add_refund(self, order_id: str, amount: float, currency: str, reason: str) -> dict[str, Any]:
        refund = {"refund_id": f"R-{len(self._refunds) + 1:04d}", "order_id": order_id, "amount": amount,
                  "currency": currency, "status": "sent"}
        self._refunds.append(refund)
        self._refund_keys[(order_id, float(amount))] = refund["refund_id"]
        return dict(refund)

    def refunds(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._refunds]

    def log_action(self, tool: str, args: dict[str, Any]) -> None:
        self._actions.append({"seq": len(self._actions) + 1, "tool": tool, "args": dict(args)})

    def actions(self) -> list[dict[str, Any]]:
        return [dict(a) for a in self._actions]

    def close(self) -> None:
        pass
