"""Email tool: send an email to a customer (to Mailpit in Docker), and keep a copy in the database."""
from typing import Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from ..repositories import records
from ..services.mail import deliver
from .action_log import logged
from .context import ctx_from


@tool
@logged
def send_email(to: str, subject: str, body: str, config: RunnableConfig) -> dict[str, Any]:
    """Send an email to a customer."""
    ctx = ctx_from(config)
    deliver(to, subject, body)            # raises if a mail server is configured but down
    email = records.add_email(ctx.db, ctx.ticket_id, to, subject, body)
    return {"ok": True, "message_id": f"M-{email['id']:04d}"}
