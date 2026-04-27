"""Shared LLM infrastructure + HumanGate state machine for all 3 swarm implementations.

Provides:
- EventEmitter: thread-safe SSE event queue
- call_llm / run_agent: LLM primitives using raw httpx
- HumanGate / HumanSession / HumanSessionStore: human-in-the-loop state machine
- HumanSessionStore singleton + get_session / resume_human helpers
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import httpx

# Load .env from parent directory
_dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_dotenv_path):
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path)

API_BASE = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1")
API_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")
DEFAULT_MODEL = "gemma4:31b:cloud"
TIMEOUT = 120.0
MAX_RETRIES = 3
MAX_CONCURRENT = 5

_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


# =============================================================================
# LLM Primitives
# =============================================================================

class EventEmitter:
    """Thread-safe event emitter that queues events for SSE delivery."""
    def __init__(self):
        self._queues: list[asyncio.Queue] = []
    def subscribe(self):
        q = asyncio.Queue(); self._queues.append(q); return q
    def unsubscribe(self, q):
        if q in self._queues: self._queues.remove(q)
    def emit(self, event):
        for q in self._queues: q.put_nowait(event)


async def call_llm(client: httpx.AsyncClient, model: str, messages: list,
                    temperature: float = 0.3, max_tokens: int = 2048) -> str:
    """Call Ollama Cloud and return the content string."""
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    for attempt in range(MAX_RETRIES):
        try:
            async with _semaphore:
                resp = await client.post(f"{API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}"}, json=body)
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"].get("content", "")
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == MAX_RETRIES - 1: return f"[API Error: {e}]"
            await asyncio.sleep(2 ** attempt)
        except httpx.HTTPStatusError as e:
            if resp.status_code == 429: await asyncio.sleep(5 * (attempt + 1)); continue
            if attempt == MAX_RETRIES - 1: return f"[HTTP {resp.status_code}]"
            await asyncio.sleep(2 ** attempt)
    return "[Failed]"


async def run_agent(client, agent_key, system_prompt, user_prompt, context="",
                    model=DEFAULT_MODEL, temperature=0.3, emitter=None, session_id="",
                    agent_name="", emoji=""):
    """Run a single agent with optional context. Returns the response text."""
    if emitter:
        emitter.emit({"type": "agent_think", "agent": agent_key,
                      "agent_name": agent_name or agent_key,
                      "message": "Preparing response...",
                      "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})

    messages = [{"role": "system", "content": system_prompt}]
    if context:
        messages.append({"role": "user", "content": f"Previous board discussion:\n{context}\n\n---\n\n{user_prompt}"})
    else:
        messages.append({"role": "user", "content": user_prompt})

    content = await call_llm(client, model, messages, temperature)

    if emitter and content:
        emitter.emit({"type": "agent_say", "agent": agent_key,
                      "agent_name": agent_name or agent_key,
                      "message": content,
                      "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})
    return content


# =============================================================================
# HumanGate State Machine
# =============================================================================

@dataclass
class HumanGate:
    """A pause point where the deliberation asks the human a question."""
    gate_id: str
    target_role: str          # e.g. "founder", "investor", "advisor"
    question: str             # The question to ask
    phase: str                # e.g. "market_due_diligence", "financial_review"
    timeout_seconds: int = 300
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HumanSession:
    """Tracks one human-in-the-loop deliberation session."""
    def __init__(self, session_id: str, topic: str, user_role: str,
                 output_expectations: str, swarm_type: str):
        self.session_id = session_id
        self.topic = topic
        self.user_role = user_role
        self.output_expectations = output_expectations
        self.swarm_type = swarm_type
        self.status: str = "idle"  # idle | running | awaiting_human | complete
        self.pending_gate: Optional[HumanGate] = None
        # All messages in order — human responses included as {"role":"user", "agent":..., "content":...}
        self.transcript: list[dict] = []
        # For Swarm 3: arbitrary key-value from human_input steps
        self.shared_context: dict[str, str] = {}
        self.processed_gates: set[str] = set()
        self._lock = asyncio.Lock()

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "user_role": self.user_role,
            "output_expectations": self.output_expectations,
            "swarm_type": self.swarm_type,
            "status": self.status,
            "pending_gate": {
                "gate_id": g.gate_id,
                "target_role": g.target_role,
                "question": g.question,
                "phase": g.phase,
                "timeout_seconds": g.timeout_seconds,
                "created_at": g.created_at,
            } if self.pending_gate else None,
            "transcript": self.transcript,
            "shared_context": self.shared_context,
        }


class HumanSessionStore:
    """In-memory store (one per server process)."""
    def __init__(self):
        self._sessions: dict[str, HumanSession] = {}

    def create(self, topic: str, user_role: str, output_expectations: str,
               swarm_type: str) -> HumanSession:
        sid = f"h-{uuid.uuid4().hex[:8]}"
        session = HumanSession(sid, topic, user_role, output_expectations, swarm_type)
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Optional[HumanSession]:
        return self._sessions.get(session_id)

    async def set_awaiting(self, session: HumanSession, gate: HumanGate):
        async with session._lock:
            session.status = "awaiting_human"
            session.pending_gate = gate

    async def resume(self, session: HumanSession, response_text: str) -> bool:
        """Inject user's response and return to running state. Idempotent by gate_id."""
        async with session._lock:
            if session.status != "awaiting_human":
                return False
            gate = session.pending_gate
            if not gate:
                return False
            if gate.gate_id in session.processed_gates:
                return True  # Already processed — idempotent
            session.processed_gates.add(gate.gate_id)

            session.transcript.append({
                "role": "user",
                "agent": gate.target_role,
                "content": response_text,
                "gate_id": gate.gate_id,
                "phase": gate.phase,
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            session.shared_context[gate.phase] = response_text
            session.pending_gate = None
            session.status = "running"
            return True

    async def complete(self, session: HumanSession):
        async with session._lock:
            session.status = "complete"
            session.pending_gate = None


# Singleton store (one per server process)
_store: Optional[HumanSessionStore] = None

def get_session_store() -> HumanSessionStore:
    global _store
    if _store is None:
        _store = HumanSessionStore()
    return _store

def get_session(session_id: str) -> Optional[HumanSession]:
    return get_session_store().get(session_id)

async def resume_human(session_id: str, gate_id: str, response_text: str) -> bool:
    """Resume a session that was awaiting human input. Returns False if not in await state."""
    session = get_session_store().get(session_id)
    if not session:
        return False
    gate = session.pending_gate
    if not gate or gate.gate_id != gate_id:
        return False
    return await get_session_store().resume(session, response_text)


def format_transcript(transcript: list[dict]) -> str:
    """Format full transcript as context for an LLM."""
    parts = []
    for entry in transcript:
        parts.append(f"## {entry['agent']}\n{entry['content']}")
    return "\n\n".join(parts)

def format_shared_context(ctx: dict) -> str:
    """Format shared_context as a readable string for Swarm 3."""
    if not ctx:
        return "No human input yet."
    parts = ["# Human Input So Far"]
    for key, val in ctx.items():
        parts.append(f"## {key}\n{val}")
    return "\n\n".join(parts)