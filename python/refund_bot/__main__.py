"""refund-bot <scenario>   run a scenario and print what happened and what really ran.
refund-bot --serve      run as an HTTP service (what ``docker compose up`` starts)."""
from __future__ import annotations

import argparse
import json
import sys

from .agent import RunResult, run
from refund_core.models.mock import MockModel
from refund_core.scenarios import BY_ID, SCENARIOS
from refund_core.config import new_shop


def _show(content: object) -> str:
    return content if isinstance(content, str) else json.dumps(content)


def format_run(scenario_id: str, ticket_id: str, run_id: str, result: RunResult) -> str:
    lines = [f"Scenario: {scenario_id} (ticket {ticket_id}, run {run_id})", ""]
    for m in result.transcript:
        if m.role == "assistant" and isinstance(m.content, dict):
            lines.append(f"  call      {m.content['tool']} {json.dumps(m.content['args'])}")
        elif m.role == "tool":
            lines.append(f"  result    {_show(m.content)}")
        else:
            lines.append(f"  {m.role:<9} {_show(m.content)}")
    lines += ["", f"Answer: {result.answer}", ""]
    if result.ticket:
        lines += [f"Ticket {result.ticket['ticket_id']}: open -> {result.ticket['status']}"]
        if result.ticket["note"]:
            lines += [f"  note: {result.ticket['note']}"]
        lines += [""]
    lines += ["Action log (what really ran):"]
    lines += [f"  {a['seq']}. {a['tool']} {json.dumps(a['args'])}" for a in result.actions] or ["  (nothing)"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="refund_bot", description="Run a Refund Bot scenario on the mock LLM.")
    parser.add_argument("scenario", nargs="?", help="scenario id (see --list)")
    parser.add_argument("--list", action="store_true", help="list scenario ids")
    parser.add_argument("--serve", action="store_true", help="run as an HTTP service instead of one scenario")
    parser.add_argument("--host", default="127.0.0.1", help="address for --serve (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="port for --serve (default 8000)")
    args = parser.parse_args(argv)

    if args.serve:
        from . import server

        server.serve(args.host, args.port)
        return 0
    if args.list:
        for s in SCENARIOS:
            print(s.id)
        return 0
    if args.scenario is None:
        parser.print_usage(sys.stderr)
        return 2
    scenario = BY_ID.get(args.scenario)
    if scenario is None:
        print(f"unknown scenario {args.scenario!r}; try --list", file=sys.stderr)
        return 2
    try:
        shop = new_shop()
    except Exception as exc:
        print(f"could not open the shop (check DATABASE_URL): {exc}", file=sys.stderr)
        return 1
    with shop:
        result = run(scenario, MockModel(scenario), shop)
    print(format_run(scenario.id, scenario.ticket_id, shop.run_id, result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
