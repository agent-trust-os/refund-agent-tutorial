"""The types the mock models share. They are small on purpose: a message, a tool spec, and the two things a
model can answer with (a tool call or a final answer). ``chat.py`` turns them into LangChain messages."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class Message:
    role: str                      # "user" | "assistant" | "tool"
    content: Any
    tool_call_id: str | None = None


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]     # a JSON Schema object: {"properties": {...}, "required": [...]}


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
