"""Pick the model for a run: the rule-based mock, or Claude through LangChain.

LLM_PROVIDER=mock (default) needs nothing. anthropic needs ANTHROPIC_API_KEY and the ``llm`` extra
(``uv sync --extra llm``). auto uses anthropic if ANTHROPIC_API_KEY is set, and the mock otherwise.
"""
from __future__ import annotations

import os

from langchain_core.language_models import BaseChatModel

from ..core.config import get_settings
from .chat import ModelChat
from .rules import RuleModel


class ModelError(Exception):
    """The model asked for cannot be created."""


def get_model() -> BaseChatModel:
    settings = get_settings()
    provider = settings.llm_provider
    if provider == "auto":
        provider = "anthropic" if os.environ.get("ANTHROPIC_API_KEY") else "mock"
    if provider == "mock":
        return ModelChat(brain=RuleModel())
    if provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise ModelError("LLM_PROVIDER=anthropic needs ANTHROPIC_API_KEY")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise ModelError("LLM_PROVIDER=anthropic needs the llm extra: uv sync --extra llm") from exc
        return ChatAnthropic(model=settings.llm_model, temperature=0)
    raise ModelError(f"unknown LLM_PROVIDER {provider!r}: use mock, anthropic or auto")
