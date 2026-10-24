"""What every tool gets besides the model's arguments: the database, the ticket being worked on, and the request.

The graph passes them in the run's ``configurable`` settings, so the model never sees them.
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session


@dataclass
class ToolContext:
    db: Session
    ticket_id: str | None    # the ticket the agent is resolving; refunds, emails and actions are linked to it
    request: str = ""        # the original request ("Resolve support ticket T-1."): AgentTrust reads it as the tool's input


def ctx_from(config: RunnableConfig) -> ToolContext:
    settings = config["configurable"]
    return ToolContext(settings["db"], settings.get("ticket_id"), settings.get("request", ""))
