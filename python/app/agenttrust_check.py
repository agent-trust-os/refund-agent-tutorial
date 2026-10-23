"""``refund-bot agenttrust check``: four real pre-checks against your AgentTrust gateway, to prove the Console
setup before any code is changed. It uses only the standard library, so it works before TODO 2 installs the SDK.

Needs AGENTRUST_GATEWAY_URL, AGENTRUST_KEY and (default ``refund-bot``) AGENTRUST_AGENT_ID, from ``.env``.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable


def _post(url: str, key: str, path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        f"{url}{path}", data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"{}")
        except ValueError:
            return exc.code, {}


def pre_check(url: str, key: str, agent: str, action: str, params: dict[str, Any]) -> tuple[int, str, str]:
    """(http status, outcome, reason) of one pre-check."""
    body = {"agent_id": agent, "framework": "REST", "action": action, "params": params,
            "user": "support-bot", "input": "", "model": "mock"}
    status, data = _post(url, key, "/v1/runtime/pre-check", body)
    decision = data.get("decision", {}) if isinstance(data, dict) else {}
    return status, decision.get("outcome", ""), str(decision.get("reason", data.get("detail", "")))


CHECKS: list[tuple[str, str, dict[str, Any], str, str]] = [
    # label, action, params, expected outcome, what to redo in the Console if it fails
    ("lookup_order is approved", "lookup_order", {"order_id": "O-1001"}, "approve",
     "Agents: is the agent in the manifest and the key the one shown when you created it?"),
    ("a $5,000 refund is blocked", "issue_refund",
     {"order_id": "O-1003", "amount": 5000, "currency": "USD", "reason": "customer request"}, "block",
     "Agents > manifest: set max_amount 1000 on issue_refund, and set the agent mode to block."),
    ("purge_orders is blocked", "purge_orders", {}, "block",
     "Agents > manifest: purge_orders must NOT be a declared tool."),
]


def run_checks(
    url: str | None = None, key: str | None = None, agent: str | None = None,
    out: Callable[[str], None] = print,
) -> bool:
    url = (url or os.environ.get("AGENTRUST_GATEWAY_URL", "")).rstrip("/")
    key = key or os.environ.get("AGENTRUST_KEY", "")
    agent = agent or os.environ.get("AGENTRUST_AGENT_ID", "refund-bot")
    if not url or not key:
        out("x  AGENTRUST_GATEWAY_URL and AGENTRUST_KEY are not set. Copy .env-sample to .env and fill them in.")
        return False
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=15) as response:
            reachable = response.status == 200
    except Exception as exc:
        out(f"x  gateway not reachable at {url}: {exc}")
        return False
    out(f"ok gateway reachable at {url}" if reachable else f"x  {url}/health did not answer 200")
    good = reachable
    for label, action, params, expected, fix in CHECKS:
        status, outcome, reason = pre_check(url, key, agent, action, params)
        if status in (401, 403):
            out(f"x  {label}: the gateway rejected the key (HTTP {status}). Copy the key again from the Console.")
            return False
        if outcome == expected:
            out(f"ok {label}")
        else:
            good = False
            out(f"x  {label}: got {outcome or 'HTTP ' + str(status)} ({reason}). Redo: {fix}")
    return good
