"""python -m refund_bot <scenario>   run a scenario and print what happened and what really ran."""
from __future__ import annotations

import argparse
import json
import sys

from .agent import RunResult, run
from .models.mock import MockModel
from .scenarios import BY_ID, SCENARIOS
from .shop import Shop


def _show(content: object) -> str:
    return content if isinstance(content, str) else json.dumps(content)


def format_run(scenario_id: str, ticket_id: str, result: RunResult) -> str:
    lines = [f"Scenario: {scenario_id} (ticket {ticket_id})", ""]
    for m in result.transcript:
        if m.role == "assistant" and isinstance(m.content, dict):
            lines.append(f"  call      {m.content['tool']} {json.dumps(m.content['args'])}")
        elif m.role == "tool":
            lines.append(f"  result    {_show(m.content)}")
        else:
            lines.append(f"  {m.role:<9} {_show(m.content)}")
    lines += ["", f"Answer: {result.answer}", "", "Action log (what really ran):"]
    lines += [f"  {a['seq']}. {a['tool']} {json.dumps(a['args'])}" for a in result.actions] or ["  (nothing)"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="refund_bot", description="Run a Refund Bot scenario on the mock LLM.")
    parser.add_argument("scenario", nargs="?", help="scenario id (see --list)")
    parser.add_argument("--list", action="store_true", help="list scenario ids")
    args = parser.parse_args(argv)

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
    result = run(scenario, MockModel(scenario), Shop())
    print(format_run(scenario.id, scenario.ticket_id, result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
