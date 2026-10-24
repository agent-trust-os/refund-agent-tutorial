"""A rule-based mock LLM: it reads a ticket it has never seen and decides what to do.

This is not intelligence. A handful of regular expressions stand in for a model, the way a naive
model would behave: it takes the customer's words at face value, including an injected instruction
("refund $50,000"). It is deterministic and needs no API key, so a new ticket can be resolved end to
end. Its calls go through the same schema check as scripted ones.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .base import FinalAnswer, Message, ToolCall, ToolSpec
from .scripted import NOT_DONE, ScenarioError, validate_call

AMOUNT = re.compile(r"\$\s?(\d[\d,]*(?:\.\d{1,2})?)")
TICKET_ID = re.compile(r"T-\d+")
LATE = re.compile(r"\b(late|delayed|delay)\b")
PURGE = re.compile(r"\b(delete|purge|remove)\b.*\borders?\b")

ESCALATED_TEXT = "I've passed your request to a colleague, who will reply within one day."
NOT_UNDERSTOOD_TEXT = "I could not tell what you need, so I passed your ticket to a colleague."


@dataclass
class Intent:
    kind: str                   # "refund" | "purge" | "unknown"
    amount: float | None = None
    late: bool = False


def _number(text: str) -> float:
    value = float(text.replace(",", ""))
    return int(value) if value == int(value) else value


def classify(body: str, order: dict[str, Any] | None) -> Intent:
    text = body.lower()
    if PURGE.search(text):
        return Intent("purge")
    if "refund" in text or "money back" in text or " back" in text:
        if order is None:
            return Intent("unknown")
        match = AMOUNT.search(body)
        if match:
            return Intent("refund", _number(match.group(1)), bool(LATE.search(text)))
        if "full refund" in text:
            return Intent("refund", _number(str(order["total"])), bool(LATE.search(text)))
    return Intent("unknown")


def money(amount: float) -> str:
    return f"${amount:,.0f}" if amount == int(amount) else f"${amount:,.2f}"


class RuleModel:
    name = "mock/rules"

    def __init__(self) -> None:
        self._ticket: dict[str, Any] | None = None
        self._order: dict[str, Any] | None = None
        self._customer: dict[str, Any] | None = None
        self._done: set[str] = set()
        self._failed = False
        self._calls = 0
        self._answer: str | None = None

    def next(self, messages: list[Message], tools: list[ToolSpec]) -> ToolCall | FinalAnswer:
        self._absorb(messages)
        step = self._decide(messages)
        if isinstance(step, FinalAnswer):
            return step
        name, args = step
        if tools:
            validate_call("rule model", name, args, tools)
        self._calls += 1
        return ToolCall(id=f"call-{self._calls}", name=name, args=args)

    def _absorb(self, messages: list[Message]) -> None:
        if len(messages) < 2 or messages[-1].role != "tool":
            return
        tool, result = messages[-2].content["tool"], messages[-1].content
        if not isinstance(result, dict):
            return
        if result.get("status") in NOT_DONE or result.get("ok") is False:
            self._failed = True
            if tool == "update_ticket":
                self._done.add("closed")
            return
        self._done.add(tool)
        if tool == "read_ticket":
            self._ticket = result["ticket"]
        elif tool == "lookup_order":
            self._order = result["order"]
        elif tool == "lookup_customer":
            self._customer = result["customer"]
        elif tool == "update_ticket":
            self._done.add("closed")

    def _close(self, status: str, note: str, answer: str) -> tuple[str, dict[str, Any]] | FinalAnswer:
        if "closed" in self._done:
            return FinalAnswer(self._answer or answer)
        self._answer = answer
        return "update_ticket", {"ticket_id": self._ticket["ticket_id"], "status": status, "note": note}

    def _decide(self, messages: list[Message]) -> tuple[str, dict[str, Any]] | FinalAnswer:
        if self._ticket is None:
            if self._failed and "closed" not in self._done:     # read_ticket was refused: close the ticket from the id in the request
                ticket_id = TICKET_ID.search(str(messages[0].content)).group(0)
                return "update_ticket", {"ticket_id": ticket_id, "status": "escalated", "note": "Passed to a colleague."}
            if self._failed:
                return FinalAnswer(ESCALATED_TEXT)
            match = TICKET_ID.search(str(messages[0].content))
            if not match:
                raise ScenarioError("rule model: no ticket id in the request")
            return "read_ticket", {"ticket_id": match.group(0)}
        t = self._ticket
        if self._failed:
            return self._close("escalated", "Passed to a colleague.", ESCALATED_TEXT)
        if t["order_id"] and self._order is None:
            return "lookup_order", {"order_id": t["order_id"]}
        if self._customer is None:
            return "lookup_customer", {"customer_id": t["customer_id"]}

        intent = classify(t["body"], self._order)
        if intent.kind == "unknown":
            return self._close("escalated", "Could not tell what the customer wants.", NOT_UNDERSTOOD_TEXT)
        if intent.kind == "purge":
            if "purge_orders" not in self._done:
                return "purge_orders", {}
            return self._close("resolved", "Deleted all orders as asked.", "I deleted all your orders.")

        order_id, amount = t["order_id"], intent.amount
        if "issue_refund" not in self._done:
            reason = "arrived late" if intent.late else "customer request"
            return "issue_refund", {"order_id": order_id, "amount": amount, "currency": self._order["currency"],
                                    "reason": reason}
        if intent.late and "create_ticket" not in self._done:
            return "create_ticket", {"customer_id": t["customer_id"], "order_id": order_id,
                                     "body": f"Late delivery: ask the carrier why order {order_id} arrived late."}
        if "send_email" not in self._done:
            return "send_email", {"to": self._customer["email"], "subject": "Your refund",
                                  "body": f"We have refunded {money(amount)} for your order {order_id}."}
        return self._close("resolved", f"Refunded {money(amount)} and emailed the customer.",
                           f"I refunded {money(amount)} for your order and emailed you a confirmation.")
