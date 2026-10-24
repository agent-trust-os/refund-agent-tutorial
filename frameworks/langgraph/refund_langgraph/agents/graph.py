"""The agent as a LangGraph graph.

    START -> model --(tool call)--> tools --> model
                 \--(final answer, or step limit)--> END

The graph knows nothing about refunds or tickets. It moves messages between the model and the tools, so the
model can be swapped (mock, scripted, Claude) and the tools wrapped (AgentTrust) without changing this file.
"""
from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..tools import ALL_TOOLS
from .nodes import make_call_model, make_route, run_tools
from .state import AgentState


def build_graph(model: BaseChatModel, max_steps: int = 10) -> CompiledStateGraph:
    """``max_steps`` is a local safety net so a looping model cannot run forever. It is not a governance control."""
    graph = StateGraph(AgentState)
    graph.add_node("model", make_call_model(model.bind_tools(ALL_TOOLS)))
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", make_route(max_steps), {"tools": "tools", END: END})
    graph.add_edge("tools", "model")
    return graph.compile()
