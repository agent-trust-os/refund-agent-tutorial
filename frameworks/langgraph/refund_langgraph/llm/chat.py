"""Mock models as LangChain chat models, and the conversion between LangChain messages and ours.

``ModelChat`` wraps a mock ``Model`` (the rule-based one, or a scripted scenario) so the graph can treat it
exactly like a real chat model: ``bind_tools`` gives it the tool schemas, ``invoke`` returns an ``AIMessage``
that is either a final answer or carries ``tool_calls``.
"""
from __future__ import annotations

import json
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool

from .base import FinalAnswer, Message, ToolSpec


def text_of(message: BaseMessage) -> str:
    """The text of a message. Real models may answer with a list of content blocks."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in content)


def parse_result(content: Any) -> Any:
    """A tool message holds the tool's result as JSON text. Anything else (a LangChain error) becomes an ERROR."""
    try:
        value = json.loads(content) if isinstance(content, str) else content
    except ValueError:
        value = None
    return value if isinstance(value, dict) else {"status": "ERROR", "reason": str(content)}


def to_messages(messages: list[AnyMessage]) -> list[Message]:
    """LangChain messages as our messages: one per user text, tool call, tool result and answer."""
    out: list[Message] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            out.append(Message("user", text_of(m)))
        elif isinstance(m, AIMessage) and m.tool_calls:
            out += [Message("assistant", {"tool": c["name"], "args": c["args"]}, tool_call_id=c["id"])
                    for c in m.tool_calls]
        elif isinstance(m, AIMessage):
            out.append(Message("assistant", text_of(m)))
        elif isinstance(m, ToolMessage):
            out.append(Message("tool", parse_result(m.content), tool_call_id=m.tool_call_id))
    return out


def spec_of(tool: BaseTool) -> ToolSpec:
    """The JSON schema a mock model checks its calls against, taken from the LangChain tool."""
    schema = tool.tool_call_schema.model_json_schema()
    return ToolSpec(tool.name, tool.description.splitlines()[0],
                    {"type": "object", "properties": schema.get("properties", {}),
                     "required": schema.get("required", [])})


class ModelChat(BaseChatModel):
    brain: Any                          # a mock ``Model``: has ``name`` and ``next(messages, specs)``
    specs: list[ToolSpec] = []

    @property
    def _llm_type(self) -> str:
        return self.brain.name

    def bind_tools(self, tools: list[BaseTool], **kwargs: Any) -> "ModelChat":
        return self.model_copy(update={"specs": [spec_of(t) for t in tools]})

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager: Any = None,
                  **kwargs: Any) -> ChatResult:
        step = self.brain.next(to_messages(messages), self.specs)
        if isinstance(step, FinalAnswer):
            message = AIMessage(content=step.text)
        else:
            message = AIMessage(content="", tool_calls=[
                {"id": step.id, "name": step.name, "args": step.args, "type": "tool_call"}])
        return ChatResult(generations=[ChatGeneration(message=message)])
