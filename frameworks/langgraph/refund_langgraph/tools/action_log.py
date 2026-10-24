"""The action log: one row per tool call, written before the tool runs, and the wrapper that does it.

It is the proof of what really happened, whatever the agent or the model says. Tests and the tutorial
read it to check what ran, and later, what AgentTrust stopped.
"""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from ..repositories import records
from .context import ToolContext, ctx_from


def log_action(ctx: ToolContext, tool: str, args: dict[str, Any]) -> None:
    records.add_action(ctx.db, ctx.ticket_id, tool, args)


def logged(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Wrap a tool function (its last parameter is ``config``): log the call, run it, and turn an exception
    into an ERROR result so the model can recover instead of the graph crashing."""
    signature = inspect.signature(fn)

    @functools.wraps(fn)
    def call(*args: Any, config: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            bound = signature.bind(*args, config=config, **kwargs)
            bound.apply_defaults()
            visible = {k: v for k, v in bound.arguments.items() if k != "config"}
            log_action(ctx_from(config), fn.__name__, visible)
            return fn(*args, config=config, **kwargs)
        except Exception as exc:
            return {"status": "ERROR", "tool": fn.__name__, "reason": str(exc)}

    return call
