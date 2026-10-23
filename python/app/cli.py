"""The ``refund-bot`` command.

    refund-bot serve                         start the web app on http://localhost:8000
    refund-bot scenarios                     list the seven scripted scenarios
    refund-bot run over_limit                play one scenario (on a throwaway database)
    refund-bot ticket "text" --customer C-1 --order O-1001
                                             a customer writes in, and the agent resolves the ticket
    refund-bot tickets [--status open]       list tickets
    refund-bot reset                         delete everything and put the starting data back
    refund-bot agenttrust check              prove the AgentTrust Console setup (four pre-checks)

Data goes to DATABASE_URL (default: the file refund_bot.db in this folder).
"""
from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy.exc import OperationalError

from .agents.state import RunResult
from .core.config import get_settings
from .core.env import load_env
from .db.seed import reset_database
from .db.session import database
from .llm.scenarios import SCENARIOS
from .repositories import tickets
from .services.scenarios import play_scenario
from .services.tickets import TicketError, resolve_ticket, submit_ticket


def show(result: RunResult) -> str:
    """A run as text: each tool call and its result, the answer, the ticket, and the action log."""
    lines = [f"Ticket {result.ticket_id}", ""]
    for m in result.transcript:
        if m.role == "assistant" and isinstance(m.content, dict):
            lines.append(f"  call      {m.content['tool']} {json.dumps(m.content['args'])}")
        elif m.role == "tool":
            lines.append(f"  result    {json.dumps(m.content)}")
        else:
            lines.append(f"  {m.role:<9} {m.content}")
    lines += ["", f"Answer: {result.answer}", ""]
    if result.ticket:
        lines.append(f"Ticket {result.ticket['ticket_id']}: open -> {result.ticket['status']}")
        if result.ticket["note"]:
            lines.append(f"  note: {result.ticket['note']}")
        lines.append("")
    for t in result.created_tickets:
        lines.append(f"Created ticket {t['ticket_id']} ({t['status']}): {t['body']}")
    if result.created_tickets:
        lines.append("")
    # TODO(AgentTrust 11/11): print each decision's envelope id and its Console link. Paste from docs/guides/direct-api.html#todo-11
    lines.append("Action log (what really ran):")
    lines += [f"  {n}. {a['tool']} {json.dumps(a['args'])}" for n, a in enumerate(result.actions, 1)] or ["  (nothing)"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="refund-bot", description="The Refund Bot support agent.")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="start the web app")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("scenarios", help="list the scripted scenarios")
    run = commands.add_parser("run", help="play a scripted scenario")
    run.add_argument("scenario")
    ticket = commands.add_parser("ticket", help="submit a ticket and let the agent resolve it")
    ticket.add_argument("text")
    ticket.add_argument("--customer", required=True, help="for example C-1")
    ticket.add_argument("--order", default="", help="for example O-1001")
    listing = commands.add_parser("tickets", help="list tickets")
    listing.add_argument("--status", choices=["open", "resolved", "escalated"])
    # TODO(AgentTrust 6/11): add --governed to "ticket" (harness now, client in TODO 9). Paste from docs/guides/harness.html#todo-6
    commands.add_parser("reset", help="put the starting data back")
    agenttrust = commands.add_parser("agenttrust", help="AgentTrust helpers")
    agenttrust.add_argument("action", choices=["check"])
    load_env()
    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        from .core.logging import setup_logging

        setup_logging()
        uvicorn.run("app.main:app", host=args.host, port=args.port)
        return 0
    if args.command == "agenttrust":
        from .agenttrust_check import run_checks

        return 0 if run_checks() else 1
    if args.command == "scenarios":
        for s in SCENARIOS:
            print(f"{s.id:<16} ticket {s.ticket_id}")
        return 0
    try:
        if args.command == "run":
            print(show(play_scenario(args.scenario)))
            return 0
        with database(get_settings().database_url)() as db:
            if args.command == "ticket":
                created = submit_ticket(db, args.customer, args.text, args.order)
                print(f"Submitted ticket {created['ticket_id']} for {args.customer}: {args.text}\n")
                print(show(resolve_ticket(db, created["ticket_id"])))
            elif args.command == "tickets":
                for t in tickets.list_tickets(db, args.status):
                    print(f"{t['ticket_id']}  {t['status']:<10} {t['customer_id']:<4} {t['order_id'] or '-':<7} {t['body'][:60]}")
            elif args.command == "reset":
                reset_database(db)
                print("The database is back to its starting data.")
    except TicketError as exc:
        print(exc.message, file=sys.stderr)
        return 2
    except OperationalError as exc:
        print(f"could not open the database (check DATABASE_URL): {exc.orig}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
