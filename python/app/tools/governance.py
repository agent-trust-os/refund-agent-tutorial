"""AgentTrust governance for the tools: each tool is wrapped so AgentTrust is asked before it runs."""
from __future__ import annotations

import functools
import os
from typing import Any, Callable

from ..core.config import get_settings

Tool = Callable[..., dict[str, Any]]


class GovernanceNotConfigured(RuntimeError):
    """AgentTrust is asked for, but the gateway url or the key is missing."""


def governed_harness(tool: Tool) -> Tool:
    """Guard a tool with ``@harness``: AgentTrust is asked before it runs, and again with what it returned.

    A refused call comes back as a BLOCKED result and a gateway that cannot be reached as UNAVAILABLE, so
    the agent loop and the model see a normal tool result instead of an exception.
    """
    settings = get_settings()
    if not settings.agentrust_gateway_url or not settings.agentrust_key:
        raise GovernanceNotConfigured("set AGENTRUST_GATEWAY_URL and AGENTRUST_KEY in .env (see .env-sample)")
    os.environ.setdefault("AGENTRUST_FAILURE_MODE", settings.agentrust_failure_mode)
    from agentrust_sdk import BlockedError, GatewayUnavailableError, harness

    guarded = harness(
        agent_id=settings.agentrust_agent_id,
        action=tool.__name__,
        base_url=settings.agentrust_gateway_url,
        api_key=settings.agentrust_key,
        block_on_block=True,        # a block stops the call
        block_on_review=True,       # so does "a person must look first": the SDK default lets it through
        raise_on_error=True,        # a failing check stops the call: the SDK default runs the tool anyway
    )(tool)

    @functools.wraps(tool)
    def call(*args: Any, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("user", "support-bot")        # @harness reads the user only from the keyword arguments
        try:
            return guarded(*args, **kwargs)
        except BlockedError as exc:
            return {"status": "BLOCKED", "tool": tool.__name__, "reason": exc.reason, "outcome": exc.outcome}
        except GatewayUnavailableError as exc:
            return {"status": "UNAVAILABLE", "tool": tool.__name__, "reason": str(exc)}
        except Exception as exc:                        # the check itself failed: do not run the tool
            return {"status": "UNAVAILABLE", "tool": tool.__name__, "reason": f"AgentTrust check failed: {exc}"}

    return call

# TODO(AgentTrust 8/11): add governed_client(fn): the same guard with AgentTrustClient. Paste from docs/guides/direct-api.html#todo-8
