"""Swarm 3: Self-Generating — MAS²-inspired (human-in-the-loop)

A meta-agent (the Generator) DESIGNS the deliberation structure based on the idea.
An Implementor EXECUTES it. A Rectifier CORRECTS mid-deliberation.
Human input is injected as human_input plan steps.

Key differences from other swarms:
- The deliberation STRUCTURE is generated per-idea by a meta-agent
- Human's role and expectations are inputs to the Generator
- The Generator can plan `human_input` steps at natural pause points
- This is genuinely different because the flow changes completely per idea
"""
from __future__ import annotations
import asyncio, json, os, re, importlib, uuid
from datetime import datetime, timezone
import httpx, sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from shared_llm import (EventEmitter, call_llm, run_agent, DEFAULT_MODEL, TIMEOUT, API_KEY,
                        HumanSession, HumanGate, resume_human, format_shared_context)

# Load agents from THIS directory
_this = os.path.dirname(os.path.abspath(__file__))
_import_spec = importlib.util.spec_from_file_location("swarm3_agents", os.path.join(_this, "agents.py"))
_swarm3_agents = importlib.util.module_from_spec(_import_spec)
_import_spec.loader.exec_module(_swarm3_agents)
AGENT_POOL = _swarm3_agents.AGENT_POOL


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

    while True:
        await asyncio.sleep(0.5)
        async with session._lock:
            if session.status != "awaiting_human":
                for entry in reversed(session.transcript):
                    if entry.get("gate_id") == gate_id:
                        return entry["content"]
                return ""

def _parse_plan(plan_text):
    """Parse the LLM-generated plan into executable steps."""
    steps = []
    current_step = None
    for line in plan_text.split("\n"):
        line = line.strip()
        # Match step headers like "Step 1:", "STEP 2:", "## Step 1"
        m = re.match(r"(?:##\s*)?(?:STEP|Step)\s*(\d+)\s*[:\-]?\s*(.*)", line)
        if m:
            if current_step:
                steps.append(current_step)
            current_step = {
                "step": int(m.group(1)),
                "label": m.group(2).strip(),
                "agents": [],
                "parallel": False,
                "prompt_hint": "",
            }
            continue
        # Match agent assignments like "Agent: CEO", "Agents: CTO, CFO"
        if current_step:
            m2 = re.match(r"Agents?\s*[:\-]\s*(.+)", line, re.IGNORECASE)
            if m2:
                agent_names = [a.strip().upper() for a in re.split(r"[,;&]", m2.group(1))]
                for ak, agent in AGENT_POOL.items():
                    if agent["name"].upper() in agent_names or ak.upper() in agent_names:
                        current_step["agents"].append(ak)
                # Check for "human" agent (marks this as a human_input step)
                if any("HUMAN" in n for n in agent_names):
                    current_step["agents"] = ["human_input"]
                current_step["parallel"] = len(current_step["agents"]) > 1 and current_step["agents"][0] != "human_input"
                continue
            m3 = re.match(r"(?:Mode|Execution)\s*[:\-]\s*(parallel|sequential)", line, re.IGNORECASE)
            if m3:
                current_step["parallel"] = m3.group(1).lower() == "parallel"
                continue
            m4 = re.match(r"(?:Prompt|Focus|Task)\s*[:\-]\s*(.+)", line, re.IGNORECASE)
            if m4:
                current_step["prompt_hint"] = m4.group(1).strip()
                continue
            if line and not current_step["prompt_hint"] and not current_step["agents"]:
                current_step["prompt_hint"] = line
    if current_step:
        steps.append(current_step)
    return steps


async def run_deliberation(idea, session_id, session_dir, emitter=None, human_session=None):
    """
    human_session: HumanSession object if human-in-the-loop, else None.
    If provided, the Generator is told the user's role + expectations,
    and human_input steps are injected at natural pause points.
    """
    os.makedirs(session_dir, exist_ok=True)
    all_outputs = {}
    plan_steps = []
    use_human = human_session is not None

    def emit(ev):
        ev["ts"] = datetime.now(timezone.utc).isoformat()
        ev["session_id"] = session_id
        if emitter: emitter.emit(ev)

    emit({"type": "session_start", "idea": idea})
    emit({"type": "architecture", "name": "Self-Generating",
          "description": "MAS²: meta-agent designs the deliberation structure. Plan is generated per-idea, executed by Implementor, corrected by Rectifier."})

    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as client:

        # === PHASE 1: GENERATOR creates the deliberation plan ===
        emit({"type": "phase_start", "phase": "generation", "label": "Generator Designs Plan"})

        generator_sys = (
            "You are the GENERATOR — a meta-agent that designs deliberation plans. "
            "Given a startup idea, you create a STEP-BY-STEP plan specifying:\n"
            "- Which agents participate in each step\n"
            "- Whether they run in parallel or sequential\n"
            "- What each agent should focus on\n\n"
            "Available agents: " + ", ".join(f"{a['name']} ({a['role']})" for a in AGENT_POOL.values()) + "\n\n"
            "CRITICAL RULES:\n"
            "- CEO ALWAYS goes first (opening pitch)\n"
            "- Board Chair ALWAYS goes last (final resolution)\n"
            "- Not every idea needs every agent. Be SELECTIVE.\n"
            "- 3-6 steps total. Keep it focused.\n"
            "- Choose agents based on the IDEA'S domain, not a default roster.\n\n"
            "You may add ONE 'human_input' step at a natural pause point (e.g., after CEO pitch or after first analysis round). "
            "Use it for facts only the human founder can provide.\n\n"
            "Format each step as:\n"
            "Step N: [label]\n"
            "Agents: [comma-separated agent names, or 'human' for human_input]\n"
            "Mode: parallel OR sequential\n"
            "Prompt: [what they should focus on]"
        )

        user_context = ""
        if use_human:
            default_exp = human_session.output_expectations or "raw transcript"
            user_context = (
                f"\n\nHuman participant: role='{human_session.user_role}', "
                f"output_expectations='{default_exp}'"
            )

        plan_resp = await run_agent(client, "generator", generator_sys,
            f"Design a deliberation plan for: **{idea}**. "
            f"Output the step-by-step plan. Be specific about which agents and what prompts.{user_context}",
            "", emitter=emitter, session_id=session_id, agent_name="Generator")
        all_outputs["generator"] = [plan_resp]

        # Parse the plan
        plan_steps = _parse_plan(plan_resp)
        if not plan_steps:
            # Fallback plan
            plan_steps = [
                {"step": 1, "label": "Opening Pitch", "agents": ["ceo"], "parallel": False, "prompt_hint": "Pitch the idea"},
                {"step": 2, "label": "Cross-Examination", "agents": ["cto", "cfo", "cro"], "parallel": True, "prompt_hint": "Challenge feasibility"},
                {"step": 3, "label": "Closing", "agents": ["ceo"], "parallel": False, "prompt_hint": "Address objections"},
                {"step": 4, "label": "Resolution", "agents": ["board_chair"], "parallel": False, "prompt_hint": "Final verdict"},
            ]

        emit({"type": "plan_generated", "plan": plan_steps,
              "plan_text": plan_resp[:500]})
        emit({"type": "phase_end", "phase": "generation"})

        # Save the plan
        with open(os.path.join(session_dir, "plan.json"), "w", encoding="utf-8") as f:
            json.dump(plan_steps, f, indent=2)

        # === PHASE 2: IMPLEMENTOR executes the plan ===
        emit({"type": "phase_start", "phase": "execution", "label": "Implementor Executes Plan"})
        context_parts = []

        for step in plan_steps:
            step_num = step["step"]
            step_label = step.get("label", f"Step {step_num}")
            step_agents = step.get("agents", [])
            is_parallel = step.get("parallel", False)
            prompt_hint = step.get("prompt_hint", "")

            emit({"type": "step_start", "step": step_num, "label": step_label,
                  "agents": [AGENT_POOL.get(a, {}).get("name", a) for a in step_agents] if step_agents and step_agents[0] != "human_input" else ["Human Founder"],
                  "parallel": is_parallel})

            ctx = "\n\n".join(context_parts) if context_parts else ""

            # Human input step — pause and ask user
            if step_agents and step_agents[0] == "human_input":
                question = f"{prompt_hint or 'Please answer the board\'s question.'}\nIdea: {idea}"
                if use_human:
                    answer = await _await_human(human_session, f"step_{step_num}", question, emitter, session_id)
                    context_parts.append(f"## {human_session.user_role}\n{answer}")
                    all_outputs.setdefault("human_founder", []).append(answer)
                else:
                    # No human session — skip with a note
                    context_parts.append(f"## [Human Founder skipped — no user session]")
                emit({"type": "step_end", "step": step_num})
            elif is_parallel and len(step_agents) > 1:
                tasks = []
                for ak in step_agents:
                    if ak not in AGENT_POOL:
                        continue
                    agent = AGENT_POOL[ak]
                    prompt = f"For the startup idea **{idea}**: {prompt_hint}. 200-300 words."
                    tasks.append((ak, run_agent(client, ak, agent["system"], prompt, ctx,
                        emitter=emitter, session_id=session_id, agent_name=agent["name"],
                        temperature=agent["temperature"])))
                if tasks:
                    results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
                    for (ak, _), res in zip(tasks, results):
                        text = str(res) if isinstance(res, Exception) else res
                        context_parts.append(f"## {AGENT_POOL[ak]['name']}\n{text}")
                        all_outputs.setdefault(ak, []).append(text)
            else:
                for ak in step_agents:
                    if ak not in AGENT_POOL:
                        continue
                    agent = AGENT_POOL[ak]
                    prompt = f"For the startup idea **{idea}**: {prompt_hint}. 200-300 words."
                    text = await run_agent(client, ak, agent["system"], prompt, ctx,
                        emitter=emitter, session_id=session_id, agent_name=agent["name"],
                        temperature=agent["temperature"])
                    context_parts.append(f"## {agent['name']}\n{text}")
                    all_outputs.setdefault(ak, []).append(text)
                    ctx = "\n\n".join(context_parts)

            emit({"type": "step_end", "step": step_num})

            # === RECTIFIER check after each step ===
            if step_num >= 2 and step_num < len(plan_steps):
                rectifier_sys = (
                    "You are the RECTIFIER — you monitor deliberation quality. "
                    "Given the current discussion, decide if the remaining plan needs modification. "
                    "Respond with either 'CONTINUE' (plan is fine) or 'MODIFY: [specific changes]'."
                )
                rect_check = await run_agent(client, "rectifier", rectifier_sys,
                    f"Current deliberation on **{idea}**:\n{ctx}\n\n"
                    f"Remaining steps: {json.dumps(plan_steps[step_num:], default=str)}\n\n"
                    "Does the plan need modification? CONTINUE or MODIFY: [changes].",
                    "", emitter=emitter, session_id=session_id, agent_name="Rectifier")

                if "MODIFY:" in rect_check.upper():
                    # Try to parse modifications (simple: skip next step or adjust prompt)
                    emit({"type": "rectification", "rectifier_response": rect_check[:200]})
                    all_outputs.setdefault("rectifier", []).append(rect_check)
                    # Simple modification: if rectifier says skip, mark next step agents as empty
                    if "SKIP" in rect_check.upper():
                        plan_steps[step_num]["agents"] = []
                        emit({"type": "step_skipped", "step": step_num + 1})

        emit({"type": "phase_end", "phase": "execution"})

    emit({"type": "session_done"})

    # Save transcript
    with open(os.path.join(session_dir, "transcript.md"), "w", encoding="utf-8") as f:
        f.write(f"# Self-Generating Deliberation — {idea}\n\nSession: {session_id}\n")
        f.write(f"Steps generated: {len(plan_steps)}\n\n")
        f.write("## Generated Plan\n\n")
        for step in plan_steps:
            agents_str = ", ".join(AGENT_POOL.get(a, {}).get("name", a) for a in step.get("agents", []))
            f.write(f"### Step {step['step']}: {step.get('label', '')}\n")
            f.write(f"- Agents: {agents_str}\n")
            f.write(f"- Mode: {'Parallel' if step.get('parallel') else 'Sequential'}\n")
            f.write(f"- Focus: {step.get('prompt_hint', '')}\n\n")
        f.write("---\n\n")
        for ak, responses in all_outputs.items():
            name = AGENT_POOL.get(ak, {}).get("name", ak)
            for i, text in enumerate(responses):
                label = f" ({i+1})" if len(responses) > 1 else ""
                f.write(f"## {name}{label}\n\n{text}\n\n---\n\n")
    return all_outputs