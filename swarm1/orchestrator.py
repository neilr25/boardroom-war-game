"""Swarm 1: Dynamic Swarm — AgentSpawn-inspired (human-in-the-loop)

Board Chair ANALYSES the idea, DYNAMICALLY DECIDES which specialists to summon.
Only summoned agents participate. Agents can REQUEST_SUBAGENT for deep dives.
Chair can RECALL agents for follow-up questions.
Chair can ASK human directly (via RECALL: human_founder - question).
The roster changes per idea — NOT a fixed pipeline.
"""
from __future__ import annotations
import asyncio, json, os, re, sys, importlib, uuid
from datetime import datetime, timezone
import httpx

# Load shared LLM from parent
_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from shared_llm import (EventEmitter, call_llm, run_agent, DEFAULT_MODEL, TIMEOUT, API_KEY,
                        HumanSession, HumanGate, resume_human)

# Load agents from THIS directory using direct import to avoid parent shadow
_this = os.path.dirname(os.path.abspath(__file__))
_import_spec = importlib.util.spec_from_file_location("swarm1_agents", os.path.join(_this, "agents.py"))
_swarm1_agents = importlib.util.module_from_spec(_import_spec)
_import_spec.loader.exec_module(_swarm1_agents)
BASE_AGENTS = _swarm1_agents.BASE_AGENTS

# Add human as a special "virtual" agent for the Chair's RECALL
HUMAN_AGENT_KEY = "human_founder"
HUMAN_AGENT = {
    "name": "Human Founder",
    "emoji": "👤",
    "color": "#64748b",
    "model": DEFAULT_MODEL,
    "temperature": 0.5,
    "system": (
        "You are the human founder pitching the startup idea. "
        "You answer questions from the board directly and factually. "
        "You are NOT the CEO agent — you are the actual person behind the pitch. "
        "When the Chair RECALLs you, answer the specific question asked."
    ),
}

# The orchestrator calls this when it needs a human answer.
# It sets the session to awaiting_human, emits a human_gate event,
# and polls until resume_human is called.
async def _await_human(session, phase: str, question: str, emitter, session_id: str) -> str:
    gate_id = f"hg-{uuid.uuid4().hex[:8]}"
    gate = HumanGate(gate_id=gate_id, target_role=session.user_role,
                      question=question, phase=phase)
    async with session._lock:
        session.status = "awaiting_human"
        session.pending_gate = gate

    if emitter:
        emitter.emit({
            "type": "human_gate",
            "gate_id": gate_id,
            "target_role": session.user_role,
            "question": question,
            "phase": phase,
            "user_role": session.user_role,
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
        })

    # Poll until resume
    while True:
        await asyncio.sleep(0.5)
        async with session._lock:
            if session.status != "awaiting_human":
                for entry in reversed(session.transcript):
                    if entry.get("gate_id") == gate_id:
                        return entry["content"]
                return ""

def _parse_summons(text):
    """Extract which agents the Chair wants to summon."""
    summoned = []
    for line in text.split("\n"):
        for key, agent in BASE_AGENTS.items():
            if key == "board_chair": continue
            if agent["name"].lower() in line.lower() and key not in summoned:
                summoned.append(key)
    return summoned or ["ceo", "cto", "cfo", "cro", "customer", "counsel"]

def _parse_subagent_requests(text):
    """Extract REQUEST_SUBAGENT: role - task from any agent's response."""
    requests = []
    for m in re.finditer(r"REQUEST_SUBAGENT:\s*(.+?)\s*[-–]\s*(.+)", text):
        role = re.sub(r"[*`\[\]]", "", m.group(1).strip())
        task = m.group(2).strip()
        if role and task:
            requests.append({"role": role, "task": task})
    return requests

def _parse_recalls(text):
    """Extract RECALL: agent - question from Chair's response."""
    recalls = []
    for line in text.split("\n"):
        if "RECALL:" in line.upper():
            for key, agent in BASE_AGENTS.items():
                clean_line = re.sub(r"[*`\[\]]", "", line).lower()
                if agent["name"].lower() in clean_line:
                    question = line.split("-", 1)[-1].strip() if "-" in line else "Please elaborate."
                    question = re.sub(r"^RECALL:\s*", "", question, flags=re.IGNORECASE).strip()
                    recalls.append((key, question))
    return recalls


async def run_deliberation(idea, session_id, session_dir, emitter=None, human_session=None):
    """
    human_session: HumanSession object if human-in-the-loop, else None.
    When human_session is provided, the Chair can RECALL the human directly
    and the user's output_expectations shape the resolution prompt.
    """
    os.makedirs(session_dir, exist_ok=True)
    context_parts = []
    all_outputs = {}
    active_agents = {"board_chair": BASE_AGENTS["board_chair"]}
    dynamic_agents = {}
    use_human = human_session is not None

    def emit(ev):
        ev["ts"] = datetime.now(timezone.utc).isoformat()
        ev["session_id"] = session_id
        if emitter: emitter.emit(ev)

    emit({"type": "session_start", "idea": idea})
    emit({"type": "architecture", "name": "Dynamic Swarm", "description": "Chair dynamically spawns specialists based on idea complexity. Agents can request sub-agents for deep dives."})

    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as client:

        # === PHASE 1: Chair analyses idea and decides WHO to summon ===
        emit({"type": "phase_start", "phase": "chair_analysis", "label": "Chair Analyses & Summons"})
        chair_prompt = (
            f"A startup idea has been submitted for board evaluation: **{idea}**\n\n"
            "As Board Chair, ANALYSE this idea and decide which specialists to SUMMON.\n\n"
            "First, briefly assess: what kind of expertise does this idea require?\n"
            "Then list the specialists who should participate. Format each on its own line:\n"
            "SUMMON: CEO\n"
            "SUMMON: CTO\n"
            "etc.\n\n"
            "Be SELECTIVE. A consumer app doesn't need a patent lawyer. "
            "A fintech doesn't need a hardware expert. Only summon what's needed.\n"
            "CEO is always needed for the pitch."
        )
        chair_resp = await run_agent(client, "board_chair", BASE_AGENTS["board_chair"]["system"],
            chair_prompt, emitter=emitter, session_id=session_id, agent_name="Board Chair")
        context_parts.append(f"## Board Chair (Analysis)\n{chair_resp}")
        all_outputs["board_chair"] = [chair_resp]

        summoned = _parse_summons(chair_resp)
        if "ceo" not in summoned: summoned.insert(0, "ceo")
        for ak in summoned:
            active_agents[ak] = BASE_AGENTS[ak]

        emit({"type": "agents_summoned", "agents": [BASE_AGENTS[a]["name"] for a in summoned if a in BASE_AGENTS]})
        emit({"type": "phase_end", "phase": "chair_analysis"})

        # === PHASE 2: CEO pitches ===
        emit({"type": "phase_start", "phase": "ceo_pitch", "label": "CEO Opening Pitch"})
        ctx = "\n\n".join(context_parts)
        ceo_resp = await run_agent(client, "ceo", BASE_AGENTS["ceo"]["system"],
            f"Deliver your Opening Pitch for: **{idea}**. Problem, solution, ask, confidence (1-5). 200-400 words.",
            ctx, emitter=emitter, session_id=session_id, agent_name="CEO", temperature=0.7)
        context_parts.append(f"## CEO\n{ceo_resp}")
        all_outputs.setdefault("ceo", []).append(ceo_resp)
        emit({"type": "phase_end", "phase": "ceo_pitch"})

        # === PHASE 3: Summoned specialists cross-examine (parallel) ===
        emit({"type": "phase_start", "phase": "cross_exam", "label": "Specialists Cross-Examine"})
        ctx = "\n\n".join(context_parts)
        prompts_map = {
            "cto": "Cross-examine technical feasibility. 200-300 words.",
            "cfo": "Stress-test financial viability. 200-300 words.",
            "cro": "Evaluate GTM strategy. 200-300 words.",
            "customer": "Reality-check from buyer's perspective. 200-300 words.",
            "counsel": "Audit legal/regulatory risks. 200-300 words.",
        }
        tasks = []
        for ak in summoned:
            if ak in prompts_map:
                tasks.append((ak, run_agent(client, ak, BASE_AGENTS[ak]["system"],
                    f"Cross-examine **{idea}**: {prompts_map[ak]}", ctx,
                    emitter=emitter, session_id=session_id, agent_name=BASE_AGENTS[ak]["name"],
                    temperature=BASE_AGENTS[ak]["temperature"])))
        if tasks:
            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            for (ak, _), res in zip(tasks, results):
                text = str(res) if isinstance(res, Exception) else res
                context_parts.append(f"## {BASE_AGENTS[ak]['name']}\n{text}")
                all_outputs.setdefault(ak, []).append(text)

                # Check for sub-agent requests (max 2 total to prevent runaway)
                sub_requests = _parse_subagent_requests(text)[:2]
                if sub_requests:
                    sub_tasks = []
                    for req in sub_requests:
                        role, task_desc = req["role"], req["task"]
                        sub_key = f"sub_{role.lower().replace(' ', '_')}"
                        sub_sys = f"You are {role}, a specialist sub-agent. Focus on: {task_desc}. Be concise. 100-200 words."
                        emit({"type": "subagent_spawned", "parent": ak, "role": role, "task": task_desc})
                        sub_tasks.append((sub_key, role, task_desc,
                            run_agent(client, sub_key, sub_sys,
                                f"The {BASE_AGENTS[ak]['name']} requested deep-dive on: {task_desc}\nIdea: **{idea}**. 100-200 words.",
                                "\n\n".join(context_parts), emitter=emitter, session_id=session_id, agent_name=role)))
                    sub_results = await asyncio.gather(*[t[3] for t in sub_tasks], return_exceptions=True)
                    for (sub_key, role, task_desc, _), res in zip(sub_tasks, sub_results):
                        text2 = str(res) if isinstance(res, Exception) else res
                        context_parts.append(f"## {role} (sub-agent)\n{text2}")
                        all_outputs.setdefault(sub_key, []).append(text2)
                        dynamic_agents[sub_key] = {"name": role, "task": task_desc}

        emit({"type": "phase_end", "phase": "cross_exam"})

        # === PHASE 4: Chair checks if follow-up needed ===
        emit({"type": "phase_start", "phase": "followup", "label": "Chair Follow-up"})
        ctx = "\n\n".join(context_parts)
        followup = await run_agent(client, "board_chair", BASE_AGENTS["board_chair"]["system"],
            "Based on the cross-exams, RECALL any agent with a follow-up question? "
            "Format: RECALL: [agent name] - [question]. Or say PROCEED TO REBUTTAL.\n"
            "IMPORTANT: If you need facts only the founder can provide (unit economics, differentiation, roadmap), "
            "RECALL the human founder.",
            ctx, emitter=emitter, session_id=session_id, agent_name="Board Chair")
        context_parts.append(f"## Board Chair (Follow-up)\n{followup}")
        all_outputs.setdefault("board_chair", []).append(followup)

        # Handle RECALLS — including human founder
        for ak, question in _parse_recalls(followup):
            if ak in active_agents:
                recall_resp = await run_agent(client, ak, BASE_AGENTS[ak]["system"],
                    f"The Chair asks: {question}", "\n\n".join(context_parts),
                    emitter=emitter, session_id=session_id, agent_name=BASE_AGENTS[ak]["name"],
                    temperature=BASE_AGENTS[ak]["temperature"])
                context_parts.append(f"## {BASE_AGENTS[ak]['name']} (Follow-up)\n{recall_resp}")
                all_outputs.setdefault(ak, []).append(recall_resp)

        # Human founder RECALL — pause and ask user
        if use_human:
            human_recalls = [q for (ak, q) in _parse_recalls(followup) if ak == HUMAN_AGENT_KEY or HUMAN_AGENT_KEY in ak]
            if not human_recalls:
                # Also check raw text for "RECALL: human" patterns
                for line in followup.split("\n"):
                    if "RECALL:" in line.upper() and "human" in line.lower():
                        m = re.search(r"RECALL:\s*.+?\s*[-–]\s*(.+)", line, re.IGNORECASE)
                        if m:
                            human_recalls.append(m.group(1).strip())
                        else:
                            human_recalls.append("Please answer the board's question about your startup.")

            for question in human_recalls[:2]:  # max 2 human pauses per session
                answer = await _await_human(human_session, "followup", question, emitter, session_id)
                context_parts.append(f"## {human_session.user_role}\n{answer}")
                all_outputs.setdefault(HUMAN_AGENT_KEY, []).append(answer)

        emit({"type": "phase_end", "phase": "followup"})

        # === PHASE 5: CEO rebuttal ===
        emit({"type": "phase_start", "phase": "rebuttal", "label": "CEO Closing Rebuttal"})
        ctx = "\n\n".join(context_parts)
        rebuttal = await run_agent(client, "ceo", BASE_AGENTS["ceo"]["system"],
            "Address TOP 3 objections. Confidence delta (-3 to +3). 200-400 words.",
            ctx, emitter=emitter, session_id=session_id, agent_name="CEO", temperature=0.7)
        context_parts.append(f"## CEO (Rebuttal)\n{rebuttal}")
        all_outputs.setdefault("ceo", []).append(rebuttal)
        emit({"type": "phase_end", "phase": "rebuttal"})

        # === PHASE 6: Chair resolution ===
        resolution_prompt_suffix = ""
        if use_human and human_session.output_expectations:
            resolution_prompt_suffix = (
                f"\n\nUser's requested output format: **{human_session.output_expectations}**. "
                "Format your final resolution to match this expectation precisely."
            )

        emit({"type": "phase_start", "phase": "resolution", "label": "Final Resolution"})
        ctx = "\n\n".join(context_parts)
        resolution = await run_agent(client, "board_chair", BASE_AGENTS["board_chair"]["system"],
            "Issue Final Resolution. APPROVED/REJECTED/CONDITIONAL, funding, risk, vote tally. 300-500 words."
            + resolution_prompt_suffix,
            ctx, emitter=emitter, session_id=session_id, agent_name="Board Chair")
        context_parts.append(f"## Board Chair (Resolution)\n{resolution}")
        all_outputs.setdefault("board_chair", []).append(resolution)
        emit({"type": "phase_end", "phase": "resolution"})

    emit({"type": "session_done"})

    # Save transcript
    with open(os.path.join(session_dir, "transcript.md"), "w", encoding="utf-8") as f:
        f.write(f"# Dynamic Swarm Deliberation — {idea}\n\nSession: {session_id}\n")
        f.write(f"Agents summoned: {', '.join(BASE_AGENTS[a]['name'] for a in summoned if a in BASE_AGENTS)}\n")
        f.write(f"Sub-agents spawned: {', '.join(v['name'] for v in dynamic_agents.values()) or 'none'}\n\n---\n\n")
        for ak, responses in all_outputs.items():
            name = active_agents.get(ak, {}).get("name", ak)
            emoji = active_agents.get(ak, {}).get("emoji", "")
            for i, text in enumerate(responses):
                label = f" ({i+1})" if len(responses) > 1 else ""
                f.write(f"## {emoji} {name}{label}\n\n{text}\n\n---\n\n")
    return all_outputs