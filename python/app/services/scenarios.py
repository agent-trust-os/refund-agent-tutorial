"""Play one of the seven scripted scenarios on a throwaway in-memory database.

Scenarios are self-contained demos: each starts from the starting data and never touches your real
tickets and orders, even ``purge``. Emails are still delivered to Mailpit when SMTP_HOST is set.
"""
from __future__ import annotations

from ..agents.state import RunResult
from ..agents.support_agent import run
from ..db.session import open_database
from ..llm.scenarios import BY_ID
from ..llm.scripted import ScriptedModel
from .tickets import TicketError


def play_scenario(scenario_id: str) -> RunResult:
    scenario = BY_ID.get(scenario_id)
    if scenario is None:
        raise TicketError(f"unknown scenario {scenario_id!r}", 404)
    with open_database("sqlite://")() as db:
        return run(scenario.ticket_id, ScriptedModel(scenario), db)
