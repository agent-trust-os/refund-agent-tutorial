"""Run the graph on one ticket and collect everything it did."""
from __future__ import annotations

import logging

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.orm import Session

from ..llm.chat import text_of, to_messages
from ..llm.factory import get_model
from ..repositories import records, tickets
from .graph import build_graph
from .prompts import ticket_request
from .state import RunResult

STEP_LIMIT_ANSWER = "Stopped: step limit reached"

log = logging.getLogger("refund_bot.agent")


def run(ticket_id: str, db: Session, model: BaseChatModel | None = None, max_steps: int = 10) -> RunResult:
    """Work on one ticket until the model gives its final answer."""
    model = model or get_model()
    before = {t["ticket_id"] for t in tickets.list_tickets(db)}
    request = ticket_request(ticket_id)
    log.info("%s | start | model=%s", ticket_id, getattr(model, "_llm_type", type(model).__name__))

    final = build_graph(model, max_steps).invoke(
        {"messages": [HumanMessage(request)], "steps": 0},
        config={"configurable": {"db": db, "ticket_id": ticket_id, "request": request},
                "recursion_limit": 2 * max_steps + 5})

    last = final["messages"][-1]
    answer = text_of(last) if isinstance(last, AIMessage) and not last.tool_calls else STEP_LIMIT_ANSWER
    ticket = tickets.get_ticket(db, ticket_id)
    log.info("%s | done  | ticket %s | answer: %s", ticket_id, ticket["status"] if ticket else "missing", answer)
    return RunResult(
        ticket_id=ticket_id,
        transcript=to_messages(final["messages"]),
        answer=answer,
        ticket=ticket,
        actions=records.list_actions(db, ticket_id=ticket_id),
        created_tickets=[t for t in tickets.list_tickets(db) if t["ticket_id"] not in before],
    )
