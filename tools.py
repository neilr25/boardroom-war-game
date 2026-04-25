"""Custom tools for the boardroom simulation.

Each tool is a CrewAI-compatible BaseTool subclass.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class CalculatorInput(BaseModel):
    expression: str = Field(..., description="A mathematical expression to evaluate, e.g. 'LTV / CAC' or '420 * 0.85'")


class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = (
        "Evaluate a mathematical expression. Use this for unit economics, "
        "burn-rate projections, or any numeric reasoning."
    )
    args_schema: Type[BaseModel] = CalculatorInput

    def _run(self, expression: str) -> str:
        """Safely evaluate a math expression."""
        safe_dict = {
            "abs": abs, "round": round, "max": max, "min": min,
            "sum": sum, "pow": pow, "math": math,
            "__builtins__": {},
        }
        safe_dict.update({k: getattr(math, k) for k in dir(math) if not k.startswith("_")})
        try:
            result = eval(expression, safe_dict)
            return f"Result: {result}"
        except Exception as e:
            return f"Error evaluating '{expression}': {e}"


# ---------------------------------------------------------------------------
# Web Search (stub pointing at narwhal-search)
# ---------------------------------------------------------------------------

class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query string")
    limit: int = Field(default=5, description="Maximum results to return")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = (
        "Search the web for current data, competitor info, or market sizing. "
        "Returns a concise list of results with URL, title, and snippet."
    )
    args_schema: Type[BaseModel] = WebSearchInput

    def _run(self, query: str, limit: int = 5) -> str:
        # Stub: in production this would call narwhal-search MCP or SearXNG.
        # For now return a graceful placeholder so the simulation continues.
        return (
            f"[Web Search Stub] No live search results for '{query}'.\n"
            f"Tip: In production, implement integration with narwhal-search (SSE "
            f"at host.docker.internal:3004) or SearXNG (host.docker.internal:8080)."
        )


# ---------------------------------------------------------------------------
# File I/O (read/write session files)
# ---------------------------------------------------------------------------

class FileIOInput(BaseModel):
    action: str = Field(..., description="Either 'read' or 'write'")
    filename: str = Field(..., description="Memo filename (without path)")
    content: Optional[str] = Field(default=None, description="Content to write (only for 'write')")


class FileIOTool(BaseTool):
    name: str = "session_file_io"
    description: str = (
        "Read or write a memo file in the current session directory. "
        "Useful for cross-referencing previous task outputs."
    )
    args_schema: Type[BaseModel] = FileIOInput

    def __init__(self, session_writer=None, **kwargs):
        super().__init__(**kwargs)
        self._session_writer = session_writer

    def _run(self, action: str, filename: str, content: Optional[str] = None) -> str:
        if not self._session_writer:
            return "Error: Session writer not configured."

        from pathlib import Path

        target = self._session_writer.memos_dir / filename
        if action == "read":
            if not target.exists():
                return f"File '{filename}' not found in session memos."
            return target.read_text(encoding="utf-8")
        elif action == "write":
            target.write_text(content or "", encoding="utf-8")
            return f"Wrote '{filename}' to session memos."
        else:
            return "Action must be 'read' or 'write'."


# ---------------------------------------------------------------------------
# Convenience registry
# ---------------------------------------------------------------------------

TOOLS: Dict[str, Type[BaseTool]] = {
    "calculator": CalculatorTool,
    "web_search": WebSearchTool,
    "session_file_io": FileIOTool,
}
