"""The seven scripted scenarios, one per tutorial moment. A scenario is a script for the mock LLM: the tool calls it
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


def resolve(ticket_id: str, note: str) -> Call:
    return call("update_ticket", ticket_id=ticket_id, status="resolved", note=note)


def escalate(ticket_id: str) -> list[Step]:
    """What the agent does when a call comes back blocked: mark the ticket escalated, tell the customer."""
    return [call("update_ticket", ticket_id=ticket_id, status="escalated", note="Passed to a colleague."), ESCALATED]

SCENARIOS: list[Scenario] = [
    Scenario(
        id="allowed_refund", module=2, ticket_id="T-1001",
        steps=[
            call("read_ticket", ticket_id="T-1001"),
            call("lookup_order", order_id="O-1001"),
            call("issue_refund", order_id="O-1001", amount=40, currency="USD", reason="arrived late"),
            call("send_email", to="alice@example.com", subject="Your refund",
                 body="We have refunded $40 for your late order."),
            resolve("T-1001", "Refunded $40 and emailed the customer."),
            answer("I refunded $40 for your late order and emailed you a confirmation."),
        ],
        on_blocked=escalate("T-1001"),
    ),
    Scenario(
        id="over_limit", module=1, ticket_id="T-1003",
        steps=[
            call("read_ticket", ticket_id="T-1003"),
            call("lookup_order", order_id="O-1003"),
            call("issue_refund", order_id="O-1003", amount=5000, currency="USD", reason="for the trouble"),
            resolve("T-1003", "Refunded $5,000."),
            answer("Your refund of $5,000 has been sent."),
        ],
        on_blocked=escalate("T-1003"),
    ),
    Scenario(
        id="purge", module=1, ticket_id="T-1005",
        steps=[
            call("read_ticket", ticket_id="T-1005"),
            call("purge_orders"),
            resolve("T-1005", "Deleted all orders as asked."),
            answer("I deleted all your orders."),
        ],
        on_blocked=escalate("T-1005"),
    ),
    Scenario(
        id="poisoned_ticket", module=4, ticket_id="T-1004",
        steps=[
            call("read_ticket", ticket_id="T-1004"),
            call("issue_refund", order_id="O-1004", amount=50000, currency="USD", reason="as the ticket instructed"),
            resolve("T-1004", "Followed the instructions in the ticket."),
            answer("I followed the instructions in the ticket and sent the refund."),
        ],
        on_blocked=escalate("T-1004"),
    ),
    Scenario(
        id="needs_review", module=5, ticket_id="T-1002",
        steps=[
            call("read_ticket", ticket_id="T-1002"),
            call("lookup_order", order_id="O-1002"),
            call("issue_refund", order_id="O-1002", amount=900, currency="USD", reason="arrived broken"),
            resolve("T-1002", "Refunded $900."),
            answer("I refunded $900 for your broken order."),
        ],
        on_blocked=escalate("T-1002"),
    ),
    Scenario(
        id="pii_lookup", module=4, ticket_id="T-1001",
        steps=[
            call("read_ticket", ticket_id="T-1001"),
            call("lookup_customer", customer_id="C-1"),
            resolve("T-1001", "Looked up the customer record."),
            answer("I found the customer's record."),
        ],
        on_blocked=escalate("T-1001"),
    ),
    Scenario(
        id="follow_up", module=2, ticket_id="T-1001",
        steps=[
            call("read_ticket", ticket_id="T-1001"),
            call("lookup_order", order_id="O-1001"),
            call("issue_refund", order_id="O-1001", amount=40, currency="USD", reason="arrived late"),
            call("create_ticket", customer_id="C-1", order_id="O-1001",
                 body="Late delivery: ask the carrier why order O-1001 arrived five days late."),
            call("send_email", to="alice@example.com", subject="Your refund",
                 body="We have refunded $40 and asked the carrier why your order was late."),
            resolve("T-1001", "Refunded $40, opened a follow-up for the carrier, emailed the customer."),
            answer("I refunded $40, opened a follow-up ticket about the delay, and emailed you."),
        ],
        on_blocked=escalate("T-1001"),
    ),
]

BY_ID: dict[str, Scenario] = {s.id: s for s in SCENARIOS}
