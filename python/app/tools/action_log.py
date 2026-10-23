"""The action log: one row per tool call, written before the tool runs.

It is the proof of what really happened, whatever the agent or the model says. Tests and the tutorial
read it to check what ran, and later, what AgentTrust stopped.
"""
from __future__ import annotations

from typing import Any

from ..repositories import records
from .context import ToolContext


def log_action(ctx: ToolContext, tool: str, args: dict[str, Any]) -> None:
    records.add_action(ctx.db, ctx.ticket_id, tool, args)
