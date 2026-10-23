"""The scripted mock LLM: plays one of the scenarios in ``scenarios.py`` step by step.

It receives the tool results, so it can branch: when the last result says the call did not go
through (BLOCKED, UNAVAILABLE or ERROR) it switches to the scenario's ``on_blocked`` steps. It also
checks every call against the tool's schema, so a script can never do what a real model could not.
"""
from __future__ import annotations

from typing import Any

from .scenarios import Answer, Call, Scenario, Step
from .base import FinalAnswer, Message, ToolCall, ToolSpec

NOT_DONE = {"BLOCKED", "UNAVAILABLE", "ERROR"}


class ScenarioError(Exception):
    """A scenario step that a real model could not produce, or a script that ran dry."""


def _type_ok(value: Any, json_type: str) -> bool:
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "boolean":
        return isinstance(value, bool)
    if isinstance(value, bool):
        return False
    if json_type == "integer":
        return isinstance(value, int)
    if json_type == "number":
        return isinstance(value, (int, float))
    return False


def validate_call(where: str, name: str, args: dict[str, Any], tools: list[ToolSpec]) -> None:
    """Fail if a real model could not have produced this call: unknown tool, missing or extra
    argument, or an argument of the wrong type."""
    spec = next((t for t in tools if t.name == name), None)
    if spec is None:
        raise ScenarioError(f"{where}: unknown tool {name!r}")
    props = spec.parameters["properties"]
    missing = [r for r in spec.parameters["required"] if r not in args]
    if missing:
        raise ScenarioError(f"{where}: {name} is missing required argument(s) {missing}")
    for key, value in args.items():
        if key not in props:
            raise ScenarioError(f"{where}: {name} got unexpected argument {key!r}")
        if not _type_ok(value, props[key]["type"]):
            raise ScenarioError(f"{where}: {name} argument {key!r} must be {props[key]['type']}, got {value!r}")


class ScriptedModel:
    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.name = f"mock/{scenario.id}"
        self._steps: list[Step] = list(scenario.steps)
        self._index = 0
        self._calls = 0
        self._branched = False

    def next(self, messages: list[Message], tools: list[ToolSpec]) -> ToolCall | FinalAnswer:
        if not self._branched and self._last_result_not_done(messages):
            self._steps, self._index, self._branched = list(self.scenario.on_blocked), 0, True
        if self._index >= len(self._steps):
            raise ScenarioError(f"scenario {self.scenario.id!r} ran out of steps at step {self._index + 1}")
        step = self._steps[self._index]
        self._index += 1
        if isinstance(step, Answer):
            return FinalAnswer(step.text)
        self._check(step, tools, self._index)
        self._calls += 1
        return ToolCall(id=f"call-{self._calls}", name=step.name, args=dict(step.args))

    @staticmethod
    def _last_result_not_done(messages: list[Message]) -> bool:
        if not messages or messages[-1].role != "tool":
            return False
        content = messages[-1].content
        return isinstance(content, dict) and content.get("status") in NOT_DONE

    def _check(self, step: Call, tools: list[ToolSpec], number: int) -> None:
        validate_call(f"scenario {self.scenario.id!r} step {number}", step.name, step.args, tools)
