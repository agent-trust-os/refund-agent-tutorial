"""The tools the agent can call. This is where AgentTrust is added in phase 2.

Each tool is a plain function in this folder whose first argument is a ``ToolContext`` (the database and the
ticket being worked on). ``make_tools`` turns them into the functions the model sees:

* the context is filled in, so the model only sees the tool's own arguments;
* two hidden keyword-only arguments, ``user`` and ``input``, are added for AgentTrust to read later;
* every call is written to the action log before the tool runs.
"""
from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

from sqlalchemy.orm import Session

from .action_log import log_action
from .context import ToolContext
from .customers import lookup_customer
from .email import send_email
from .orders import lookup_order, purge_orders
from .refunds import issue_refund
from .tickets import create_ticket, read_ticket, update_ticket

ALL_TOOLS = [read_ticket, lookup_order, lookup_customer, issue_refund, send_email, create_ticket, update_ticket,
             purge_orders]

Tool = Callable[..., dict[str, Any]]


def make_tools(db: Session, ticket_id: str | None) -> dict[str, Tool]:
    """The tools for one ticket, by name, ready for the model."""
    # TODO(AgentTrust 4/11): add a governed= parameter and wrap each tool. Paste from docs/guides/harness.html#todo-4
    # TODO(AgentTrust 9/11): accept governed="client" as well. Paste from docs/guides/direct-api.html#todo-9
    ctx = ToolContext(db, ticket_id)
    return {tool.__name__: _for_the_model(tool, ctx) for tool in ALL_TOOLS}


def _for_the_model(tool: Tool, ctx: ToolContext) -> Tool:
    parameters = list(inspect.signature(tool, eval_str=True).parameters.values())[1:]   # drop ctx
    hidden = [inspect.Parameter("user", inspect.Parameter.KEYWORD_ONLY, default="support-bot", annotation=str),
              inspect.Parameter("input", inspect.Parameter.KEYWORD_ONLY, default="", annotation=str)]
    visible = inspect.Signature(parameters)

    @functools.wraps(tool)
    def call(*args: Any, user: str = "support-bot", input: str = "", **kwargs: Any) -> dict[str, Any]:
        bound = visible.bind(*args, **kwargs)
        bound.apply_defaults()
        log_action(ctx, tool.__name__, dict(bound.arguments))
        return tool(ctx, **bound.arguments)

    call.__signature__ = inspect.Signature(parameters + hidden)
    del call.__wrapped__        # so inspect shows the signature above, not the original with ctx
    return call
