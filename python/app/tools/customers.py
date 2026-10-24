"""Customer tool: look up a customer."""
from __future__ import annotations

from typing import Any

from ..repositories import orders
from .context import ToolContext


def lookup_customer(ctx: ToolContext, customer_id: str) -> dict[str, Any]:
    """Look up a customer by their id."""
    customer = orders.get_customer(ctx.db, customer_id)
    # TODO(AgentTrust 5/10): do not return the SSN or the card number. Paste from docs/guides/harness.html#todo-5
    return {"ok": True, "customer": customer} if customer else {"ok": False, "error": "no such customer"}
