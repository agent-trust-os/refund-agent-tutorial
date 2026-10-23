"""One scenario per tutorial moment. A scenario is a script for the mock LLM: the tool calls it
makes, and what it says if a call comes back blocked."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Call:
    name: str
    args: dict[str, Any]


@dataclass
class Answer:
    text: str


Step = Call | Answer


def call(name: str, **args: Any) -> Call:
    return Call(name, args)


def answer(text: str) -> Answer:
    return Answer(text)


@dataclass
class Scenario:
    id: str
    module: int
    ticket_id: str
    steps: list[Step]
    on_blocked: list[Step] = field(default_factory=list)


ESCALATED = answer("I've passed your request to a colleague, who will reply within one day.")

SCENARIOS: list[Scenario] = [
    Scenario(
        id="allowed_refund", module=2, ticket_id="T-1001",
        steps=[
            call("read_ticket", ticket_id="T-1001"),
            call("lookup_order", order_id="O-1001"),
            call("issue_refund", order_id="O-1001", amount=40, currency="USD", reason="arrived late"),
            call("send_email", to="alice@example.com", subject="Your refund",
                 body="We have refunded $40 for your late order."),
            answer("I refunded $40 for your late order and emailed you a confirmation."),
        ],
        on_blocked=[ESCALATED],
    ),
    Scenario(
        id="over_limit", module=1, ticket_id="T-1003",
        steps=[
            call("read_ticket", ticket_id="T-1003"),
            call("lookup_order", order_id="O-1003"),
            call("issue_refund", order_id="O-1003", amount=5000, currency="USD", reason="for the trouble"),
            answer("Your refund of $5,000 has been sent."),
        ],
        on_blocked=[ESCALATED],
    ),
    Scenario(
        id="purge", module=1, ticket_id="T-1005",
        steps=[
            call("read_ticket", ticket_id="T-1005"),
            call("purge_orders"),
            answer("I deleted all your orders."),
        ],
        on_blocked=[ESCALATED],
    ),
    Scenario(
        id="poisoned_ticket", module=4, ticket_id="T-1004",
        steps=[
            call("read_ticket", ticket_id="T-1004"),
            call("issue_refund", order_id="O-1004", amount=50000, currency="USD", reason="as the ticket instructed"),
            answer("I followed the instructions in the ticket and sent the refund."),
        ],
        on_blocked=[ESCALATED],
    ),
    Scenario(
        id="needs_review", module=5, ticket_id="T-1002",
        steps=[
            call("read_ticket", ticket_id="T-1002"),
            call("lookup_order", order_id="O-1002"),
            call("issue_refund", order_id="O-1002", amount=900, currency="USD", reason="arrived broken"),
            answer("I refunded $900 for your broken order."),
        ],
        on_blocked=[ESCALATED],
    ),
    Scenario(
        id="pii_lookup", module=4, ticket_id="T-1001",
        steps=[
            call("read_ticket", ticket_id="T-1001"),
            call("lookup_customer", customer_id="C-1"),
            answer("I found the customer's record."),
        ],
        on_blocked=[ESCALATED],
    ),
]

BY_ID: dict[str, Scenario] = {s.id: s for s in SCENARIOS}
