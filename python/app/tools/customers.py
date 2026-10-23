"""Customer tool: look up a customer. The result includes their SSN and card number."""
from __future__ import annotations

from typing import Any

from ..repositories import orders
from .context import ToolContext


def lookup_customer(ctx: ToolContext, customer_id: str) -> dict[str, Any]:
    """Look up a customer by their id."""
    customer = orders.get_customer(ctx.db, customer_id)
    return {"ok": True, "customer": customer} if customer else {"ok": False, "error": "no such customer"}
