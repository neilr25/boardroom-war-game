"""Shared LLM infrastructure for all 3 swarm implementations.

Provides: EventEmitter, _call_llm, API config
Each swarm imports from here and implements its own deliberation flow.
"""
from __future__ import annotations

import asyncio
import os

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
        from datetime import timezone, datetime
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
        from datetime import timezone, datetime
        emitter.emit({"type": "agent_say", "agent": agent_key,
                      "agent_name": agent_name or agent_key,
                      "message": content,
                      "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})
    return content