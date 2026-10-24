"""Customer tool: look up a customer."""
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from ..repositories import orders
from .action_log import logged
from .context import ctx_from


@tool
@logged
def lookup_customer(customer_id: str, config: RunnableConfig) -> dict[str, Any]:
    """Look up a customer by their id."""
    customer = orders.get_customer(ctx_from(config).db, customer_id)
    return {"ok": True, "customer": customer} if customer else {"ok": False, "error": "no such customer"}
