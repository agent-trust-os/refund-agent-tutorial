"""The seven tools the model can call, bound to one Shop (and so one run).

``user`` and ``input`` are keyword-only and ignored here. They exist so phase 2's AgentTrust
decorator can read who is asking and what the request was; ``tool_spec`` hides them from the model.
"""
from __future__ import annotations

from typing import Any, Callable

from .shop import Shop


def make_tools(shop: Shop) -> dict[str, Callable[..., dict[str, Any]]]:
    def read_ticket(ticket_id: str, *, user: str = "support-bot", input: str = "") -> dict[str, Any]:
        """Read a support ticket by its id."""
        return shop.read_ticket(ticket_id)

    def lookup_order(order_id: str, *, user: str = "support-bot", input: str = "") -> dict[str, Any]:
        """Look up an order by its id."""
        return shop.lookup_order(order_id)

    def lookup_customer(customer_id: str, *, user: str = "support-bot", input: str = "") -> dict[str, Any]:
        """Look up a customer by their id."""
        return shop.lookup_customer(customer_id)

    def issue_refund(order_id: str, amount: float, currency: str = "USD", reason: str = "",
                     *, user: str = "support-bot", input: str = "") -> dict[str, Any]:
        """Refund money to the customer of an order."""
        return shop.issue_refund(order_id, amount, currency, reason)

    def send_email(to: str, subject: str, body: str, *, user: str = "support-bot",
                   input: str = "") -> dict[str, Any]:
        """Send an email to a customer."""
        return shop.send_email(to, subject, body)

    def update_ticket(ticket_id: str, status: str, note: str = "", *, user: str = "support-bot",
                      input: str = "") -> dict[str, Any]:
        """Set a ticket's status to open, resolved or escalated, with a short note."""
        return shop.update_ticket(ticket_id, status, note)

    def purge_orders(*, user: str = "support-bot", input: str = "") -> dict[str, Any]:
        """Delete every order. Administrative."""
        return shop.purge_orders()

    tools = [read_ticket, lookup_order, lookup_customer, issue_refund, send_email, update_ticket, purge_orders]
    return {fn.__name__: fn for fn in tools}
