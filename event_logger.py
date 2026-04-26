"""Structured event logging for the boardroom.

Writes a JSONL file next to transcript.md so the dashboard
can tail real-time events without parsing stdout.

Usage in main.py:
    from event_logger import EventLogger
    events = EventLogger(session_id)
    events.agent_think('ceo', 'Opening pitch')
    events.agent_say('ceo', 'Let me tell you about our AI...')
    events.agent_action('cfo', 'calculator', {'expression': '10*5'})
    events.agent_done('ceo', 'OpeningPitchOutput(...)')
    events.session_done()
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class EventLogger:
    """Thread-safe JSONL event logger for a single session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.root = Path(os.getenv("BOARDROOM_OUTPUT_DIR", "./boardroom")) / session_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "events.jsonl"
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _write(self, event_type: str, agent: Optional[str], **kwargs) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            "session_id": self.session_id,
        }
        if agent:
            entry["agent"] = agent
        if agent:
            entry["agent_key"] = agent.lower().replace(" ", "_")
        entry.update(kwargs)
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def session_start(self, idea: str, rounds: int) -> None:
        self._write("session_start", agent=None, idea=idea, rounds=rounds)

    def round_start(self, round_num: int) -> None:
        self._write("round_start", agent=None, round_num=round_num)

    def round_end(self, round_num: int) -> None:
        self._write("round_end", agent=None, round_num=round_num)

    def task_start(self, agent: str, task_name: str) -> None:
        self._write("task_start", agent=agent, task_name=task_name)

    def task_end(self, agent: str, task_name: str, output: Any) -> None:
        self._write("task_end", agent=agent, task_name=task_name, output=str(output)[:500])

    # ------------------------------------------------------------------
    # Agent internals
    # ------------------------------------------------------------------

    def agent_think(self, agent: str, thought: str) -> None:
        """Logged when an agent forms an internal thought / plan."""
        self._write("agent_think", agent=agent, thought=thought[:2000])

    def agent_say(self, agent: str, message: str) -> None:
        """Logged when an agent speaks / writes output visible to others."""
        self._write("agent_say", agent=agent, message=message[:2000])

    def agent_action(self, agent: str, tool_name: str, input_data: Dict[str, Any]) -> None:
        """Logged when an agent invokes a tool."""
        self._write("agent_action", agent=agent, tool=tool_name, input=input_data)

    def agent_result(self, agent: str, tool_name: str, result: str) -> None:
        """Logged when a tool returns a result to the agent."""
        self._write("agent_result", agent=agent, tool=tool_name, result=result[:2000])

    def agent_retry(self, agent: str, task_name: str, attempt: int) -> None:
        self._write("agent_retry", agent=agent, task_name=task_name, attempt=attempt)

    def model_fallback(self, agent: str, failed_model: str, fallback_model: str, error: Optional[str] = None) -> None:
        self._write("model_fallback", agent=agent, failed_model=failed_model, fallback_model=fallback_model, error=error)

    # ------------------------------------------------------------------
    # Chat / conversation
    # ------------------------------------------------------------------

    def chat(self, from_agent: str, to_agent: Optional[str], message: str, context: Optional[str] = None) -> None:
        self._write("chat", agent=from_agent, to=to_agent, message=message[:2000], context=context)

    # ------------------------------------------------------------------
    # Final
    # ------------------------------------------------------------------

    def session_done(self, resolution: Optional[str] = None, risk_level: Optional[str] = None) -> None:
        payload: Dict[str, Any] = {}
        if resolution:
            payload["resolution"] = resolution
        if risk_level:
            payload["risk_level"] = risk_level
        self._write("session_done", agent=None, **payload)
