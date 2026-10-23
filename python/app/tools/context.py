"""What every tool gets besides the model's arguments: the database, and the ticket being worked on."""
from __future__ import annotations 

from dataclasses import dataclass

from sqlalchemy.orm import Session 


@dataclass
class ToolContext:
    db: Session
    ticket_id: str | None    # the ticket the agent is resolving; refunds, emails and actions are linked to it
