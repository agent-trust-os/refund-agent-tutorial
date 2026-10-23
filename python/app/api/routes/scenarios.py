"""The seven scripted scenarios. Each runs on a throwaway database, so it never touches your data."""
from __future__ import annotations

from fastapi import APIRouter

from ...llm.scenarios import SCENARIOS
from ...schemas.data import ScenarioInfo
from ...schemas.tickets import RunResultOut
from ...services.scenarios import play_scenario
from .tickets import result_out

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioInfo])
def list_scenarios():
    return [ScenarioInfo(id=s.id, ticket_id=s.ticket_id) for s in SCENARIOS]


@router.post("/{scenario_id}/run", response_model=RunResultOut)
def run_scenario(scenario_id: str):
    return result_out(play_scenario(scenario_id))
