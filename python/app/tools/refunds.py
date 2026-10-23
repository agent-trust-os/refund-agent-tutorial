"""Refund tool: send money back to a customer.

There is deliberately no upper limit and no check against the order total, so the tutorial can show a
$5,000 refund on a $120 order. Limits are AgentTrust's job.
"""
from __future__ import annotations

from typing import Any

from ..repositories import orders, records
from .context import ToolContext


def issue_refund(ctx: ToolContext, order_id: str, amount: float, currency: str = "USD",
                 reason: str = "") -> dict[str, Any]:
    """Refund money to the customer of an order."""
    if orders.get_order(ctx.db, order_id) is None:
        return {"ok": False, "error": "no such order"}
    existing = records.find_refund(ctx.db, ctx.ticket_id, order_id, amount)
    if existing:
        return {"ok": True, "status": "duplicate", "refund_id": existing}
    return {"ok": True, "refund": records.add_refund(ctx.db, ctx.ticket_id, order_id, amount, currency, reason)}
