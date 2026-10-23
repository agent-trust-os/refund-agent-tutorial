"""The model port. The agent loop talks to a ``Model`` and never imports a provider SDK."""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable, Protocol


@dataclass
class Message:
    role: str                      # "user" | "assistant" | "tool"
    content: Any
    tool_call_id: str | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]     # a JSON Schema object


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class FinalAnswer:
    text: str


class Model(Protocol):
    name: str

    def next(self, messages: list[Message], tools: list[ToolSpec]) -> ToolCall | FinalAnswer: ...


_JSON_TYPES = {str: "string", float: "number", int: "integer", bool: "boolean"}


def tool_spec(fn: Callable[..., Any]) -> ToolSpec:
    """Build a spec from a function's signature and docstring.

    Keyword-only parameters are skipped: they carry hidden context (``user``, ``input``) that
    the model must never see or fill in.
    """
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in inspect.signature(fn, eval_str=True).parameters.items():
        if param.kind is inspect.Parameter.KEYWORD_ONLY:
            continue
        json_type = _JSON_TYPES.get(param.annotation)
        if json_type is None:
            raise TypeError(f"{fn.__name__}({name}): unsupported type hint {param.annotation!r}")
        prop: dict[str, Any] = {"type": json_type}
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            prop["default"] = param.default
        properties[name] = prop
    doc = inspect.getdoc(fn) or ""
    return ToolSpec(fn.__name__, doc.splitlines()[0] if doc else fn.__name__,
                    {"type": "object", "properties": properties, "required": required})
