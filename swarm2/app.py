"""AutoGen-inspired boardroom deliberation — direct API calls.

Uses AutoGen-style agent definitions for personas but calls Ollama Cloud directly via httpx.
This avoids the GroupChat hanging issue where AutoGen's speaker-selection LLM call blocks.
The flow is: Chair opens → CEO pitches → 5 specialists parallel → CEO rebuts → Chair resolves.
With tool use: calculator, web_search, file_writer.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from agents import AGENTS, PHASES, build_prompt
from tools import ALL_TOOLS, execute_tool, set_session_dir

API_BASE = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1")
_dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_dotenv_path):
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path)
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


async def _call_llm(client, model, messages, temperature=0.3, max_tokens=2048, tools=None):
    body = {"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
    if tools:
        body["tools"] = tools
    for attempt in range(MAX_RETRIES):
        try:
            async with _semaphore:
                resp = await client.post(f"{API_BASE}/chat/completions", headers={"Authorization": f"Bearer {API_KEY}"}, json=body)
            resp.raise_for_status()
            return resp.json()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == MAX_RETRIES - 1: return {"choices": [{"message": {"content": f"[API Error: {e}]"}}]}
            await asyncio.sleep(2 ** attempt)
        except httpx.HTTPStatusError as e:
            if resp.status_code == 429: await asyncio.sleep(5 * (attempt + 1)); continue
            if attempt == MAX_RETRIES - 1: return {"choices": [{"message": {"content": f"[HTTP {resp.status_code}]"}}]}
            await asyncio.sleep(2 ** attempt)
    return {"choices": [{"message": {"content": "[Failed]"}}]}


async def _run_agent(client, agent_key, prompt, context="", emitter=None, session_id=""):
    agent = AGENTS[agent_key]
    model = agent["model"]
    temp = agent["temperature"]

    if emitter:
        emitter.emit({"type": "agent_think", "agent": agent_key, "agent_name": agent["name"], "message": "Preparing response...", "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})

    messages = [{"role": "system", "content": agent["system"]}]
    if context: messages.append({"role": "user", "content": f"Context:\n{context}\n\n---\n\n{prompt}"})
    else: messages.append({"role": "user", "content": prompt})

    for _ in range(5):
        result = await _call_llm(client, model, messages, temp, tools=ALL_TOOLS)
        choice = result["choices"][0]["message"]
        content = choice.get("content", "")
        tool_calls = choice.get("tool_calls")
        if not tool_calls: break
        messages.append(choice)
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
            tool_result = execute_tool(fn_name, fn_args)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": tool_result})
            if emitter:
                emitter.emit({"type": "tool_use", "agent": agent_key, "agent_name": agent["name"], "tool": fn_name, "args": fn_args, "result": tool_result[:200], "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})

    if emitter and content:
        emitter.emit({"type": "agent_say", "agent": agent_key, "agent_name": agent["name"], "message": content, "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})
    return content or "[No response]"


async def run_deliberation(idea, session_id, session_dir, emitter=None):
    set_session_dir(session_dir)
    os.makedirs(session_dir, exist_ok=True)
    outputs = {}

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

            prompts = {ak: build_prompt(phase_name, ak, idea) for ak in phase_agents}

            if is_parallel and len(phase_agents) > 1:
                tasks = [_run_agent(client, ak, prompts[ak], context, emitter, session_id) for ak in phase_agents]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for ak, res in zip(phase_agents, results):
                    text = str(res) if isinstance(res, Exception) else res
                    outputs[ak] = text
                    context_parts.append(f"## {AGENTS[ak]['name']}\n{text}")
            else:
                for ak in phase_agents:
                    text = await _run_agent(client, ak, prompts[ak], context, emitter, session_id)
                    outputs[ak] = text
                    context_parts.append(f"## {AGENTS[ak]['name']}\n{text}")

            if emitter:
                emitter.emit({"type": "phase_end", "phase": phase_name, "ts": datetime.now(timezone.utc).isoformat(), "session_id": session_id})

    if emitter:
        emitter.emit({"type": "session_done", "session_id": session_id, "ts": datetime.now(timezone.utc).isoformat()})

    with open(os.path.join(session_dir, "transcript.md"), "w", encoding="utf-8") as f:
        f.write(f"# Boardroom Deliberation (AutoGen) — {idea}\n\nSession: {session_id}\n\n---\n\n")
        for ak, text in outputs.items():
            f.write(f"## {AGENTS[ak]['emoji']} {AGENTS[ak]['name']}\n\n{text}\n\n---\n\n")

    return outputs