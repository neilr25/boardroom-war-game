"""Raw asyncio orchestrator for boardroom deliberation.

No framework. Direct httpx calls to Ollama Cloud's OpenAI-compatible API.
Full tool-use loop: model calls tool → execute → feed result back → loop.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from agents import AGENTS, PHASES
from tools import ALL_TOOLS, execute_tool, set_session_dir

# --- Config ---
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
    """Thread-safe event emitter that queues events for SSE delivery."""

    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._queues:
            self._queues.remove(q)

    def emit(self, event: dict) -> None:
        for q in self._queues:
            q.put_nowait(event)


async def _call_llm(
    client: httpx.AsyncClient,
    model: str,
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 2048,
    tools: list[dict] | None = None,
    retries: int = MAX_RETRIES,
) -> dict:
    """Call Ollama Cloud's chat/completions endpoint with retry."""
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        body["tools"] = tools

    for attempt in range(retries):
        try:
            async with _semaphore:
                resp = await client.post(
                    f"{API_BASE}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}"},
                    json=body,
                )
            resp.raise_for_status()
            return resp.json()
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            if attempt == retries - 1:
                return {"error": str(e), "choices": [{"message": {"content": f"[API Error after {retries} retries: {e}]"}}]}
            await asyncio.sleep(2 ** attempt)
        except httpx.HTTPStatusError as e:
            if resp.status_code == 429:
                await asyncio.sleep(5 * (attempt + 1))
                continue
            if attempt == retries - 1:
                return {"error": str(e), "choices": [{"message": {"content": f"[HTTP {resp.status_code}: {e}]"}}]}
            await asyncio.sleep(2 ** attempt)

    return {"choices": [{"message": {"content": "[Failed after all retries]"}}]}


async def _run_agent(
    client: httpx.AsyncClient,
    agent_key: str,
    user_prompt: str,
    context: str = "",
    emitter: EventEmitter | None = None,
    session_id: str = "",
) -> str:
    """Run a single agent with tool-use loop."""
    agent = AGENTS[agent_key]
    model = agent["model"]
    temp = agent["temperature"]

    if emitter:
        emitter.emit({
            "type": "agent_think",
            "agent": agent_key,
            "agent_name": agent["name"],
            "message": f"Preparing response...",
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
        })

    messages = [
        {"role": "system", "content": agent["system"]},
    ]
    if context:
        messages.append({"role": "user", "content": f"Context from previous deliberation:\n{context}\n\n---\n\n{user_prompt}"})
    else:
        messages.append({"role": "user", "content": user_prompt})

    # Tool-use loop (max 5 tool rounds to prevent infinite loops)
    for _ in range(5):
        result = await _call_llm(client, model, messages, temp, tools=ALL_TOOLS)
        if "error" in result and "choices" not in result:
            content = f"[API Error: {result['error']}]"
            break

        choice = result["choices"][0]["message"]
        content = choice.get("content", "")
        tool_calls = choice.get("tool_calls")

        if not tool_calls:
            break

        # Execute tools
        messages.append(choice)
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
            tool_result = execute_tool(fn_name, fn_args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })
            if emitter:
                emitter.emit({
                    "type": "tool_use",
                    "agent": agent_key,
                    "agent_name": agent["name"],
                    "tool": fn_name,
                    "args": fn_args,
                    "result": tool_result[:200],
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "session_id": session_id,
                })

    # Emit agent speech
    if emitter and content:
        emitter.emit({
            "type": "agent_say",
            "agent": agent_key,
            "agent_name": agent["name"],
            "message": content,
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
        })

    return content or "[No response]"


async def run_deliberation(
    idea: str,
    session_id: str,
    session_dir: str,
    emitter: EventEmitter | None = None,
) -> dict:
    """Run the full boardroom deliberation.

    Returns a dict of {agent_key: response_text}.
    """
    set_session_dir(session_dir)
    outputs: dict[str, str] = {}

    if emitter:
        emitter.emit({
            "type": "session_start",
            "session_id": session_id,
            "idea": idea,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as client:
        context_parts = []

        for phase in PHASES:
            phase_name = phase["name"]
            phase_agents = phase["agents"]
            is_parallel = phase.get("parallel", False)

            if emitter:
                emitter.emit({
                    "type": "phase_start",
                    "phase": phase_name,
                    "label": phase["label"],
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "session_id": session_id,
                })

            context = "\n\n".join(context_parts)

            if is_parallel and len(phase_agents) > 1:
                # Run specialists in parallel
                prompts = _build_prompts(phase_name, idea, context)
                tasks = [
                    _run_agent(client, ak, prompts[ak], context, emitter, session_id)
                    for ak in phase_agents
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for ak, res in zip(phase_agents, results):
                    text = str(res) if isinstance(res, Exception) else res
                    outputs[ak] = text
                    context_parts.append(f"## {AGENTS[ak]['name']}\n{text}")
            else:
                for ak in phase_agents:
                    prompts = _build_prompts(phase_name, idea, context)
                    text = await _run_agent(client, ak, prompts[ak], context, emitter, session_id)
                    outputs[ak] = text
                    context_parts.append(f"## {AGENTS[ak]['name']}\n{text}")

            if emitter:
                emitter.emit({
                    "type": "phase_end",
                    "phase": phase_name,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "session_id": session_id,
                })

    if emitter:
        emitter.emit({
            "type": "session_done",
            "session_id": session_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    # Save transcript
    transcript_path = os.path.join(session_dir, "transcript.md")
    with open(transcript_path, "w", encoding="utf-8") as f:
        f.write(f"# Boardroom Deliberation — {idea}\n\n")
        f.write(f"Session: {session_id}\n\n---\n\n")
        for ak, text in outputs.items():
            f.write(f"## {AGENTS[ak]['name']} {AGENTS[ak]['emoji']}\n\n{text}\n\n---\n\n")

    return outputs


def _build_prompts(phase: str, idea: str, context: str) -> dict[str, str]:
    """Build user prompts for each agent in a phase."""
    prompts: dict[str, str] = {}

    if phase == "opening":
        prompts["ceo"] = (
            f"Deliver your Opening Pitch for the startup idea: **{idea}**.\n\n"
            "Cover: the headline problem, your solution, the funding ask, and your confidence level (1-5). "
            "Be compelling. Own the room. 200-400 words."
        )

    elif phase == "cross_exam":
        prompts["cto"] = (
            f"You've heard the CEO's opening pitch for **{idea}**. Now cross-examine the technical feasibility.\n\n"
            "Focus on: buildability (6-week MVP or science project?), scalability, recommended tech stack, "
            "deal-killing technical risks. Be brutal. 200-300 words."
        )
        prompts["cfo"] = (
            f"You've heard the CEO's opening pitch for **{idea}**. Now stress-test the financial viability.\n\n"
            "Focus on: unit economics (LTV/CAC), burn rate, TAM/SAM/SOM, 3-year revenue projections, "
            "financial deal-killers. Use the calculator if needed. 200-300 words."
        )
        prompts["cro"] = (
            f"You've heard the CEO's opening pitch for **{idea}**. Now evaluate the go-to-market strategy.\n\n"
            "Focus on: top 3 acquisition channels, viral coefficient estimate, CAC payback, "
            "conversion funnel observations. Demand specifics. 200-300 words."
        )
        prompts["customer"] = (
            f"You've heard the CEO's opening pitch for **{idea}**. Now reality-check it from the buyer's perspective.\n\n"
            "Focus on: switching costs, jobs-to-be-done, willingness to pay, top 3 buyer objections. "
            "Be the skeptic. 200-300 words."
        )
        prompts["counsel"] = (
            f"You've heard the CEO's opening pitch for **{idea}**. Now audit the legal, regulatory, and IP risks.\n\n"
            "Focus on: patent landscape, regulatory matrix (GDPR, SEC, industry-specific), "
            "litigation risk, non-negotiables. Find the landmine. 200-300 words."
        )

    elif phase == "rebuttal":
        prompts["ceo"] = (
            f"The board has cross-examined **{idea}**. You've heard technical, financial, GTM, customer, and legal objections.\n\n"
            "Deliver your Closing Rebuttal. Address the TOP 3 most serious objections directly. "
            "State your updated confidence delta (-3 to +3 vs opening). Be confident but not delusional. "
            "This is your last chance to save the deal. 200-400 words."
        )

    elif phase == "resolution":
        prompts["board_chair"] = (
            f"You have heard the full deliberation on **{idea}**: opening pitch, five cross-examinations, "
            "and the CEO's closing rebuttal.\n\n"
            "Issue the Final Resolution. Include:\n"
            "- Resolution: APPROVED / REJECTED / CONDITIONAL\n"
            "- Funding recommendation\n"
            "- Risk level (LOW / MEDIUM / HIGH / EXISTENTIAL)\n"
            "- Majority opinion (concise)\n"
            "- Dissenting opinion (if any)\n"
            "- Non-negotiables before wire transfer\n"
            "- Vote tally (APPROVE / REJECT / CONDITIONAL counts)\n\n"
            "Be decisive. Your word is final. 300-500 words."
        )

    return prompts