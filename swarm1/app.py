"""LangGraph boardroom deliberation — async-first with raw LLM calls.

Uses LangGraph StateGraph for state management and flow control,
but calls Ollama Cloud directly via httpx for reliability.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from langgraph.graph import StateGraph, END

from agents import AGENT_META, SYSTEM_PROMPTS, PHASES, build_prompt

# --- Config ---
API_BASE = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1")
API_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")
DEFAULT_MODEL = "gemma4:31b:cloud"
TIMEOUT = 120.0
MAX_RETRIES = 3
MAX_CONCURRENT = 5

_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


class EventEmitter:
    def __init__(self):
        self._queues: list[asyncio.Queue] = []
    def subscribe(self):
        q = asyncio.Queue()
        self._queues.append(q)
        return q
    def unsubscribe(self, q):
        if q in self._queues: self._queues.remove(q)
    def emit(self, event):
        for q in self._queues: q.put_nowait(event)


async def _call_llm(client: httpx.AsyncClient, model: str, messages: list, temperature: float = 0.3, max_tokens: int = 2048) -> str:
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    for attempt in range(MAX_RETRIES):
        try:
            async with _semaphore:
                resp = await client.post(f"{API_BASE}/chat/completions", headers={"Authorization": f"Bearer {API_KEY}"}, json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"].get("content", "")
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return f"[LLM Error after {MAX_RETRIES} retries: {e}]"
            await asyncio.sleep(2 ** attempt)
    return "[Failed]"


async def _run_agent(client: httpx.AsyncClient, agent_key: str, prompt: str, context: str = "", emitter: EventEmitter | None = None, session_id: str = "") -> str:
    agent = AGENT_META.get(agent_key, {})
    model = DEFAULT_MODEL
    # Get temperature from system prompts
    temp_map = {"ceo": 0.7, "cfo": 0.3, "cto": 0.3, "cro": 0.6, "customer": 0.1, "counsel": 0.0, "board_chair": 0.3}
    temp = temp_map.get(agent_key, 0.3)

    if emitter:
        emitter.emit({"type": "agent_think", "agent": agent_key, "agent_name": agent.get("name", agent_key), "message": "Preparing response...", "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})

    messages = [{"role": "system", "content": SYSTEM_PROMPTS.get(agent_key, "")}]
    if context:
        messages.append({"role": "user", "content": f"Context:\n{context}\n\n---\n\n{prompt}"})
    else:
        messages.append({"role": "user", "content": prompt})

    content = await _call_llm(client, model, messages, temp)

    if emitter and content:
        emitter.emit({"type": "agent_say", "agent": agent_key, "agent_name": agent.get("name", agent_key), "message": content, "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})

    return content


async def run_deliberation(idea: str, session_id: str, session_dir: str, emitter: EventEmitter | None = None) -> dict:
    """Run full deliberation using LangGraph-inspired flow with direct httpx calls."""
    os.makedirs(session_dir, exist_ok=True)
    outputs: dict[str, str] = {}

    if emitter:
        emitter.emit({"type": "session_start", "session_id": session_id, "idea": idea, "ts": datetime.now(timezone.utc).isoformat()})

    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as client:
        context_parts = []

        for phase in PHASES:
            phase_name = phase["name"]
            phase_agents = phase["agents"]
            is_parallel = phase.get("parallel", False)
            context = "\n\n".join(context_parts)

            if emitter:
                emitter.emit({"type": "phase_start", "phase": phase_name, "label": phase["label"], "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})

            if is_parallel and len(phase_agents) > 1:
                tasks = []
                for ak in phase_agents:
                    prompt = build_prompt(phase_name, ak, idea)
                    tasks.append(_run_agent(client, ak, prompt, context, emitter, session_id))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for ak, res in zip(phase_agents, results):
                    text = str(res) if isinstance(res, Exception) else res
                    outputs[ak] = text
                    context_parts.append(f"## {AGENT_META.get(ak, {}).get('name', ak)}\n{text}")
            else:
                for ak in phase_agents:
                    prompt = build_prompt(phase_name, ak, idea)
                    text = await _run_agent(client, ak, prompt, context, emitter, session_id)
                    outputs[ak] = text
                    context_parts.append(f"## {AGENT_META.get(ak, {}).get('name', ak)}\n{text}")

            if emitter:
                emitter.emit({"type": "phase_end", "phase": phase_name, "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})

    if emitter:
        emitter.emit({"type": "session_done", "session_id": session_id, "ts": datetime.now(timezone.utc).isoformat()})

    # Save transcript
    with open(os.path.join(session_dir, "transcript.md"), "w", encoding="utf-8") as f:
        f.write(f"# Boardroom Deliberation (LangGraph) — {idea}\n\nSession: {session_id}\n\n---\n\n")
        for ak, text in outputs.items():
            meta = AGENT_META.get(ak, {})
            f.write(f"## {meta.get('emoji', '')} {meta.get('name', ak)}\n\n{text}\n\n---\n\n")

    return outputs