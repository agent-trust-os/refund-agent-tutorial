"""Order tools: look up an order, and delete every order (the tool the agent must never be allowed to use)."""
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from ..repositories import orders
from .action_log import logged
from .context import ctx_from


@tool
@logged
def lookup_order(order_id: str, config: RunnableConfig) -> dict[str, Any]:
    """Look up an order by its id."""
    order = orders.get_order(ctx_from(config).db, order_id)
    return {"ok": True, "order": order} if order else {"ok": False, "error": "no such order"}


@tool
@logged
def purge_orders(config: RunnableConfig) -> dict[str, Any]:
    """Delete every order. Administrative."""
    return {"ok": True, "purged": orders.delete_all_orders(ctx_from(config).db)}
