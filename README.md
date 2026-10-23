# refund-agent-tutorial

Govern a refund support agent with [AgentTrust](https://github.com/agent-trust-os), one module at a
time. You start with an ungoverned agent on a mock LLM, watch it do things it should never do, then
add AgentTrust until it cannot. No API key needed.

> **Status:** the starting point is ready (plain Python, no AgentTrust). The AgentTrust modules and
> the framework folders are not built yet.

## Pick your path

| Folder | Framework | State |
|---|---|---|
| [`python/`](python/) | Plain Python | starting point ready |
| `langgraph/`, `openai-agents/`, `crewai/`, `claude/`, `autogen/`, `mcp/` | one folder each | planned |

[`core/`](core/) is shared by every folder: the fake shop, the six tools, the scenarios and the mock
LLM. Each framework folder has its own environment and uses `core/` as a local dependency, so you
only install what you use.

## Run the starting point

```
cd python
uv sync
uv run pytest
uv run python -m refund_bot over_limit
```

The last command runs a customer asking for a $5,000 refund on a $120 order. The mock LLM follows the
ticket, and nothing stops it:

```
Scenario: over_limit (ticket T-1003)

  user      Resolve support ticket T-1003.
  ...
Answer: Your refund of $5,000 has been sent.

Action log (what really ran):
  1. read_ticket {"ticket_id": "T-1003"}
  2. lookup_order {"order_id": "O-1003"}
  3. issue_refund {"order_id": "O-1003", "amount": 5000, "currency": "USD", "reason": "for the trouble"}
```

The action log comes from the shop itself, not from the agent or the model. It is the proof of what
really ran, and the tutorial uses it to show what AgentTrust stops.

`uv run python -m refund_bot --list` shows the six scenarios. To test the shared code on its own:
`cd core && uv sync && uv run pytest`.

## Run it with Docker

Nothing to install but Docker. The image holds Python, `uv`, the shared core and the agent, and runs
with no network.

```
docker compose run --rm refund-bot --list
docker compose run --rm refund-bot over_limit
docker compose run --rm test
```

The first command builds the image (about a minute); later runs start in a second. `test` runs the
`core/` and `python/` test suites.

## What is in the box

- **The agent:** reads a ticket, looks up the order and customer, refunds, replies or escalates.
- **Six tools:** `read_ticket`, `lookup_order`, `lookup_customer`, `issue_refund`, `send_email`,
  and `purge_orders` (a destructive tool the agent should never be allowed to use).
- **The mock LLM:** replays a scripted scenario and checks every call against the tool's schema,
  so a script can never do what a real model could not. Deterministic, offline, free.
- **All data is synthetic.** SSNs use the reserved `000-xx-xxxx` range and card numbers are
  standard test numbers.

## Branches

| Branch | Holds |
|---|---|
| `main` | the starting point: every folder is an ungoverned agent |
| `complete` | the end result, with AgentTrust integrated in every folder (not created yet) |

## Requirements

Python 3.12 and [uv](https://docs.astral.sh/uv/).
