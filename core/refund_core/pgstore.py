"""The shop's data in Postgres (tables in ``db/schema.sql``). Plain SQL through psycopg.

Every row carries the run id. Creating a store seeds that run's own copy of the fixtures, so runs
are isolated and a finished run's rows stay in the database. Money columns are ``numeric`` and come
back as plain floats so results look the same as the in-memory store.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from .fixtures import CUSTOMERS, ORDERS, TICKETS


def _plain(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {k: float(v) if isinstance(v, Decimal) else v for k, v in row.items()}


class PostgresStore:
    def __init__(self, dsn: str, run_id: str, *, seed: bool = True) -> None:
        self.run_id = run_id
        self._conn = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
        if seed:
            self._seed()

    def _seed(self) -> None:
        with self._conn.transaction(), self._conn.cursor() as cur:
            for c in CUSTOMERS.values():
                cur.execute("INSERT INTO customers VALUES (%s, %s, %s, %s, %s, %s)",
                            (self.run_id, c["customer_id"], c["name"], c["email"], c["ssn"], c["card_number"]))
            for o in ORDERS.values():
                cur.execute("INSERT INTO orders VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (self.run_id, o["order_id"], o["customer_id"], o["total"], o["currency"],
                             o["status"], o["delivered_late"]))
            for t in TICKETS.values():
                cur.execute("INSERT INTO tickets (run_id, ticket_id, customer_id, order_id, body, status, note) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (self.run_id, t["ticket_id"], t["customer_id"], t["order_id"], t["body"],
                             t["status"], t["note"]))

    def _one(self, sql: str, *params: Any) -> dict[str, Any] | None:
        return _plain(self._conn.execute(sql, params).fetchone())

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        return self._one("SELECT ticket_id, customer_id, order_id, body, status, note FROM tickets "
                         "WHERE run_id = %s AND ticket_id = %s", self.run_id, ticket_id)

    def tickets(self) -> dict[str, dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT ticket_id, customer_id, order_id, body, status, note FROM tickets "
            "WHERE run_id = %s ORDER BY ticket_id", (self.run_id,)).fetchall()
        return {r["ticket_id"]: _plain(r) for r in rows}

    def update_ticket(self, ticket_id: str, status: str, note: str) -> dict[str, Any] | None:
        return self._one("UPDATE tickets SET status = %s, note = %s WHERE run_id = %s AND ticket_id = %s "
                         "RETURNING ticket_id, customer_id, order_id, body, status, note",
                         status, note, self.run_id, ticket_id)

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        return self._one("SELECT order_id, customer_id, total, currency, status, delivered_late FROM orders "
                         "WHERE run_id = %s AND order_id = %s", self.run_id, order_id)

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        return self._one("SELECT customer_id, name, email, ssn, card_number FROM customers "
                         "WHERE run_id = %s AND customer_id = %s", self.run_id, customer_id)

    def orders(self) -> dict[str, dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT order_id, customer_id, total, currency, status, delivered_late FROM orders "
            "WHERE run_id = %s ORDER BY order_id", (self.run_id,)).fetchall()
        return {r["order_id"]: _plain(r) for r in rows}

    def purge_orders(self) -> int:
        return self._conn.execute("DELETE FROM orders WHERE run_id = %s", (self.run_id,)).rowcount

    def find_refund(self, order_id: str, amount: float) -> str | None:
        row = self._conn.execute("SELECT refund_id FROM refunds WHERE run_id = %s AND order_id = %s AND amount = %s",
                                 (self.run_id, order_id, Decimal(str(amount)))).fetchone()
        return row["refund_id"] if row else None

    def add_refund(self, order_id: str, amount: float, currency: str, reason: str) -> dict[str, Any]:
        count = self._conn.execute("SELECT count(*) AS n FROM refunds WHERE run_id = %s", (self.run_id,)).fetchone()["n"]
        refund_id = f"R-{count + 1:04d}"
        self._conn.execute("INSERT INTO refunds (run_id, refund_id, order_id, amount, currency, reason, status) "
                           "VALUES (%s, %s, %s, %s, %s, %s, 'sent')",
                           (self.run_id, refund_id, order_id, Decimal(str(amount)), currency, reason))
        return {"refund_id": refund_id, "order_id": order_id, "amount": amount, "currency": currency, "status": "sent"}

    def refunds(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT refund_id, order_id, amount, currency, status FROM refunds "
                                  "WHERE run_id = %s ORDER BY refund_id", (self.run_id,)).fetchall()
        return [_plain(r) for r in rows]

    def log_action(self, tool: str, args: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO actions (run_id, seq, tool, args) "
            "SELECT %s, COALESCE(MAX(seq), 0) + 1, %s, %s FROM actions WHERE run_id = %s",
            (self.run_id, tool, Json(args), self.run_id))

    def actions(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT seq, tool, args FROM actions WHERE run_id = %s ORDER BY seq",
                                  (self.run_id,)).fetchall()
        return [{"seq": r["seq"], "tool": r["tool"], "args": r["args"]} for r in rows]

    def close(self) -> None:
        self._conn.close()
