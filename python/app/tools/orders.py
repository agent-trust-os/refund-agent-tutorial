"""Order tools: look up an order, and delete every order (the tool the agent must never be allowed to use)."""
from __future__ import annotations

from typing import Any

from ..repositories import orders
from .context import ToolContext


def lookup_order(ctx: ToolContext, order_id: str) -> dict[str, Any]:
    """Look up an order by its id."""
    order = orders.get_order(ctx.db, order_id)
    return {"ok": True, "order": order} if order else {"ok": False, "error": "no such order"}


def purge_orders(ctx: ToolContext) -> dict[str, Any]:
    """Delete every order. Administrative."""
    return {"ok": True, "purged": orders.delete_all_orders(ctx.db)}
