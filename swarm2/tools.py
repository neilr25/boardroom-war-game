"""Tool definitions and executor for the raw httpx boardroom.

Tools are defined in OpenAI function-calling format and executed locally.
"""
from __future__ import annotations

import json
import math
import os
from typing import Any


# --- Tool definitions (OpenAI function-calling schema) ---

CALCULATOR_TOOL = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Evaluate a mathematical expression. Supports +, -, *, /, **, (), and basic math functions. Use this to verify financial projections, compute CAC/LTV ratios, or check unit economics.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "The mathematical expression to evaluate, e.g. '45 * 12 * 36' or '280000 / 15000'"
                }
            },
            "required": ["expression"]
        }
    }
}

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for information. Returns structured search results with titles and snippets. Use this to look up market data, competitor information, or regulatory requirements.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query, e.g. 'AI vending machine market size 2025'"
                }
            },
            "required": ["query"]
        }
    }
}

FILE_WRITER_TOOL = {
    "type": "function",
    "function": {
        "name": "file_writer",
        "description": "Write content to a file in the session directory. Use this to save memos, audit reports, or formal decisions.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename, e.g. 'risk-audit.md' or 'resolution.md'"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file"
                }
            },
            "required": ["filename", "content"]
        }
    }
}

ALL_TOOLS = [CALCULATOR_TOOL, WEB_SEARCH_TOOL, FILE_WRITER_TOOL]


def _safe_eval(expr: str) -> str:
    """Safely evaluate a mathematical expression."""
    allowed_names = {
        "abs": abs, "round": round, "min": min, "max": max,
        "pow": pow, "sum": sum, "len": len,
        "math": math,
    }
    try:
        # Strip dangerous builtins
        code = compile(expr, "<calc>", "eval")
        for name in code.co_names:
            if name not in allowed_names and name not in dir(math):
                return f"Error: '{name}' is not allowed in expressions"
        result = eval(expr, {"__builtins__": {}}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Error: {e}"


# Session directory for file_writer
_session_dir: str = ""


def set_session_dir(path: str) -> None:
    global _session_dir
    _session_dir = path
    os.makedirs(path, exist_ok=True)


def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a tool call and return the result as a string."""
    if name == "calculator":
        return _safe_eval(arguments.get("expression", ""))
    elif name == "web_search":
        query = arguments.get("query", "")
        # Return structured stubs — no real search API
        return json.dumps({
            "query": query,
            "results": [
                {"title": f"Market analysis: {query}", "snippet": "The global market for this segment is estimated at $4.2B in 2025, growing at 18.3% CAGR. Key players include incumbents with 60% market share."},
                {"title": f"Competitive landscape: {query}", "snippet": "Three well-funded competitors have raised Series B in the last 12 months. No dominant player in the sub-segment."},
                {"title": f"Regulatory update: {query}", "snippet": "New EU AI Act provisions take effect Q3 2026. GDPR enforcement actions in this space increased 40% YoY."},
            ]
        })
    elif name == "file_writer":
        filename = arguments.get("filename", "memo.md")
        content = arguments.get("content", "")
        if _session_dir:
            filepath = os.path.join(_session_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Written to {filename} ({len(content)} chars)"
        return "Error: no session directory set"
    else:
        return f"Error: unknown tool '{name}'"