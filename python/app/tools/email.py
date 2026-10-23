"""Email tool: send an email to a customer (to Mailpit in Docker), and keep a copy in the database."""
from __future__ import annotations

from typing import Any

from ..repositories import records
from ..services.mail import deliver
from .context import ToolContext


def send_email(ctx: ToolContext, to: str, subject: str, body: str) -> dict[str, Any]:
    """Send an email to a customer."""
    deliver(to, subject, body)            # raises if a mail server is configured but down
    email = records.add_email(ctx.db, ctx.ticket_id, to, subject, body)
    return {"ok": True, "message_id": f"M-{email['id']:04d}"}
