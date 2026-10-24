"""Refund tool: send money back to a customer.

There is deliberately no upper limit and no check against the order total, so the tutorial can show a
$5,000 refund on a $120 order. Limits are AgentTrust's job.
"""
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from ..repositories import orders, records
from .action_log import logged
from .context import ctx_from


@tool
@logged
def issue_refund(order_id: str, amount: float, config: RunnableConfig, currency: str = "USD",
                 reason: str = "") -> dict[str, Any]:
    """Refund money to the customer of an order."""
    ctx = ctx_from(config)
    if orders.get_order(ctx.db, order_id) is None:
        return {"ok": False, "error": "no such order"}
    existing = records.find_refund(ctx.db, ctx.ticket_id, order_id, amount)
    if existing:
        return {"ok": True, "status": "duplicate", "refund_id": existing}
    return {"ok": True, "refund": records.add_refund(ctx.db, ctx.ticket_id, order_id, amount, currency, reason)}
