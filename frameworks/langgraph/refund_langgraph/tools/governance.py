"""AgentTrust governance for the tools. Until you fill in the TODOs below, the tools run ungoverned.

``govern`` is applied to every tool in ``__init__.py``. The tool's input for AgentTrust is the run's
``request`` (see ``context.py``); the arguments are the model's own.
"""
from __future__ import annotations

from langchain_core.tools import BaseTool


def govern(tool: BaseTool) -> BaseTool:
    """Return the tool as it is. TODO(AgentTrust): wrap its function so AgentTrust is asked before it runs."""
    return tool
