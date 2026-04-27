"""Swarm 2: Organic Conversation — Pressure-field inspired (human-in-the-loop)

No phases. No pipeline. Agents contribute to a SHARED DECISION ARTIFACT
through typed epistemic moves. Multi-round with temporal decay.

Human participates as a typed move contributor. After Round 1, the Board Chair
can issue a REQUEST move targeting the human. The orchestrator pauses,
asks the human question, and injects their typed move (ASSERT/CHALLENGE/etc.)
into the conversation transcript.
"""
from __future__ import annotations
import asyncio, json, os, re, importlib, uuid
from datetime import datetime, timezone
import httpx, sys

_parent = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _parent not in sys.path:
    sys.path.insert(0, _parent)
from shared_llm import (EventEmitter, call_llm, run_agent, DEFAULT_MODEL, TIMEOUT, API_KEY,
                       HumanSession, HumanGate, resume_human)

# Load agents from THIS directory
_this = os.path.dirname(os.path.abspath(__file__))
_import_spec = importlib.util.spec_from_file_location("swarm2_agents", os.path.join(_this, "agents.py"))
_swarm2_agents = importlib.util.module_from_spec(_import_spec)
_import_spec.loader.exec_module(_swarm2_agents)
AGENTS = _swarm2_agents.AGENTS

MOVE_TYPES = ["ASSERT", "CHALLENGE", "REFINE", "SYNTHESIZE", "CONCEDE", "REQUEST"]

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


def _parse_move(text):
    """Extract move type and content from agent response."""
    for move in MOVE_TYPES:
        if text.strip().upper().startswith(move + ":") or text.strip().upper().startswith(move + "\n"):
            content = re.sub(rf"^{move}\s*[:\-]?\s*", "", text, flags=re.IGNORECASE).strip()
            return move, content
    # Default: infer from content
    if any(w in text.lower() for w in ["however", "but", "wrong", "disagree", "challenge", "objection"]):
        return "CHALLENGE", text
    if any(w in text.lower() for w in ["refine", "adjust", "update", "modify", "improve"]):
        return "REFINE", text
    if any(w in text.lower() for w in ["synthesis", "combine", "both", "middle ground", "consensus"]):
        return "SYNTHESIZE", text
    if any(w in text.lower() for w in ["concede", "agree", "accept", "fair point"]):
        return "CONCEDE", text
    return "ASSERT", text

def _format_artifact(artifact):
    """Format the shared decision artifact for prompt injection."""
    lines = ["# Board Opinion (Living Document)", ""]
    if artifact.get("verdict"):
        lines.append(f"## Current Verdict: {artifact['verdict']}")
    if artifact.get("key_points"):
        lines.append("## Key Points")
        for pt in artifact["key_points"]:
            lines.append(f"- {pt}")
    if artifact.get("open_issues"):
        lines.append("## Open Issues")
        for iss in artifact["open_issues"]:
            lines.append(f"- {iss}")
    if artifact.get("consensus_areas"):
        lines.append("## Areas of Consensus")
        for c in artifact["consensus_areas"]:
            lines.append(f"- {c}")
    return "\n".join(lines) if len(lines) > 2 else "The board opinion is still forming."


async def run_deliberation(idea, session_id, session_dir, emitter=None, human_session=None):
    """
    human_session: HumanSession object if human-in-the-loop, else None.
    After Round 1, the Board Chair may REQUEST the human's input via a typed move.
    The human's answer is injected as a typed ASSERT move into the transcript.
    """
    os.makedirs(session_dir, exist_ok=True)
    all_outputs = {}
    artifact = {"verdict": None, "key_points": [], "open_issues": [], "consensus_areas": []}
    move_history = []
    use_human = human_session is not None

    def emit(ev):
        ev["ts"] = datetime.now(timezone.utc).isoformat()
        ev["session_id"] = session_id
        if emitter: emitter.emit(ev)

    emit({"type": "session_start", "idea": idea})
    emit({"type": "architecture", "name": "Organic Conversation",
          "description": "Pressure-field: no phases, typed epistemic moves, shared decision artifact, multi-round with temporal decay"})

    async with httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT)) as client:

        # === ROUND 0: Seed — CEO opens with an ASSERT ===
        emit({"type": "round_start", "round": 0, "label": "Opening Assertions"})
        ctx = ""
        ceo_resp = await run_agent(client, "ceo", AGENTS["ceo"]["system"],
            f"ASSERT your case for: **{idea}**. Start with ASSERT: then your argument. "
            "Problem, solution, ask, confidence (1-5). 200-400 words.",
            ctx, emitter=emitter, session_id=session_id, agent_name="CEO", temperature=0.7)
        move, content = _parse_move(ceo_resp)
        move_history.append({"agent": "ceo", "move": move, "round": 0})
        all_outputs.setdefault("ceo", []).append(ceo_resp)
        artifact["key_points"].append(f"CEO asserts: {content[:100]}")
        emit({"type": "move", "agent": "ceo", "move": move, "round": 0})
        ctx = f"## CEO\n{ceo_resp}"
        emit({"type": "round_end", "round": 0})

        # === ROUNDS 1-4: Organic multi-agent debate ===
        MAX_ROUNDS = 4
        AGENT_ORDER = ["cto", "cfo", "cro", "customer", "counsel", "board_chair"]

        for round_num in range(1, MAX_ROUNDS + 1):
            emit({"type": "round_start", "round": round_num, "label": f"Round {round_num}"})

            # In each round, ALL agents contribute (but they choose their own move type)
            # Stagger: different agents go first each round to prevent anchoring bias
            order = AGENT_ORDER[(round_num - 1):] + AGENT_ORDER[:(round_num - 1)]
            tasks = []

            for ak in order:
                agent = AGENTS[ak]
                # Build move-specific guidance
                if round_num <= 2:
                    guidance = "Choose your move: ASSERT (new claim), CHALLENGE (attack a claim), REFINE (improve a claim). Prefix your response with your move type."
                elif round_num == 3:
                    guidance = "Rounds 1-2 identified key tensions. Now REFINE or SYNTHESIZE toward consensus. CHALLENGE only if a claim is truly dangerous."
                else:
                    guidance = "Final round. SYNTHESIZE toward a verdict or CONCEDE if persuaded. The board opinion must converge."

                prompt = (
                    f"The startup idea is: **{idea}**\n\n"
                    f"{_format_artifact(artifact)}\n\n"
                    f"Round {round_num} of {MAX_ROUNDS}. {guidance}\n\n"
                    "First state your move type (ASSERT:/CHALLENGE:/REFINE:/SYNTHESIZE:/CONCEDE:), then your contribution. "
                    f"Be concise. 100-200 words."
                )
                tasks.append((ak, run_agent(client, ak, agent["system"], prompt, ctx,
                    emitter=emitter, session_id=session_id, agent_name=agent["name"],
                    temperature=agent["temperature"])))

            # Run all agents in this round in parallel
            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            for (ak, _), res in zip(tasks, results):
                text = str(res) if isinstance(res, Exception) else res
                move, content = _parse_move(text)
                move_history.append({"agent": ak, "move": move, "round": round_num})
                all_outputs.setdefault(ak, []).append(text)

                # Update shared artifact based on move
                if move == "CHALLENGE":
                    artifact["open_issues"].append(f"{AGENTS[ak]['name']}: {content[:80]}")
                elif move == "SYNTHESIZE":
                    artifact["consensus_areas"].append(f"{AGENTS[ak]['name']}: {content[:80]}")
                elif move == "CONCEDE":
                    artifact["consensus_areas"].append(f"{AGENTS[ak]['name']} concedes: {content[:80]}")
                elif move == "REFINE":
                    # Replace last key point from this agent if exists
                    existing = [p for p in artifact["key_points"] if p.startswith(AGENTS[ak]['name'])]
                    if existing:
                        artifact["key_points"] = [p for p in artifact["key_points"] if not p.startswith(AGENTS[ak]['name'])]
                    artifact["key_points"].append(f"{AGENTS[ak]['name']}: {content[:80]}")
                else:
                    artifact["key_points"].append(f"{AGENTS[ak]['name']}: {content[:80]}")

                emit({"type": "move", "agent": ak, "move": move, "round": round_num})
                ctx += f"\n\n## {AGENTS[ak]['name']} (R{round_num}, {move})\n{text}"

            # Update verdict based on round
            if round_num >= 3:
                challenges = sum(1 for m in move_history if m["move"] == "CHALLENGE" and m["round"] >= round_num - 1)
                concessions = sum(1 for m in move_history if m["move"] == "CONCEDE" and m["round"] >= round_num - 1)
                synths = sum(1 for m in move_history if m["move"] == "SYNTHESIZE" and m["round"] >= round_num - 1)
                if concessions + synths > challenges:
                    artifact["verdict"] = "LEANING APPROVED"
                elif challenges > concessions + 2:
                    artifact["verdict"] = "LEANING REJECTED"
                else:
                    artifact["verdict"] = "CONDITIONAL — KEY ISSUES UNRESOLVED"

            emit({"type": "artifact_update", "artifact": artifact, "round": round_num})
            emit({"type": "round_end", "round": round_num})

            # Human pause after Round 1 — ask for founder's context
            if use_human and round_num == 1:
                question = (
                    f"You've heard the opening assertions about **{idea}**. "
                    f"As the founder, what is your single strongest point of differentiation? "
                    f"And what is your biggest vulnerability that the board should know about?"
                )
                answer = await _await_human(human_session, "founder_context", question, emitter, session_id)
                if answer:
                    human_move_text = f"ASSERT: {answer}"
                    move, content = _parse_move(human_move_text)
                    move_history.append({"agent": "human_founder", "move": move, "round": round_num})
                    all_outputs.setdefault("human_founder", []).append(human_move_text)
                    artifact["key_points"].append(f"Founder: {content[:80]}")
                    emit({"type": "move", "agent": "human_founder", "move": move, "round": round_num})
                    ctx += f"\n\n## {human_session.user_role} (R{round_num}, {move})\n{answer}"

            # Also allow the Board Chair to REQUEST human input in Round 2+
            if use_human and round_num >= 2:
                # Check if any recent REQUEST was directed at human (parse from last few moves in ctx)
                for line in ctx.split("\n")[-20:]:
                    if "REQUEST" in line.upper() and ("human" in line.lower() or "founder" in line.lower()):
                        m = re.search(r"REQUEST[:\s]*.+?[-–]\s*(.+)", line, re.IGNORECASE)
                        if m:
                            question = m.group(1).strip()
                            if len(question) > 10:
                                answer = await _await_human(human_session, "round_question", question, emitter, session_id)
                                if answer:
                                    human_move_text = f"ASSERT: {answer}"
                                    move, content = _parse_move(human_move_text)
                                    move_history.append({"agent": "human_founder", "move": move, "round": round_num})
                                    all_outputs.setdefault("human_founder", []).append(human_move_text)
                                    ctx += f"\n\n## {human_session.user_role} (R{round_num}, {move})\n{answer}"
                        break

        # === FINAL VERDICT ===
        verdict_suffix = ""
        if use_human and human_session.output_expectations:
            verdict_suffix = (
                f"\n\nUser's requested output: **{human_session.output_expectations}**. "
                "Format your verdict to match this."
            )
        emit({"type": "phase_start", "phase": "verdict", "label": "Final Verdict"})
        ctx_final = ctx + f"\n\n# Current Board Opinion\n{_format_artifact(artifact)}"
        verdict_resp = await run_agent(client, "board_chair", AGENTS["board_chair"]["system"],
            "The board has debated for 4 rounds. Issue the FINAL VERDICT: "
            "APPROVED/REJECTED/CONDITIONAL. Funding, risk, key conditions. 300-500 words."
            + verdict_suffix,
            ctx_final, emitter=emitter, session_id=session_id, agent_name="Board Chair")
        all_outputs.setdefault("board_chair", []).append(verdict_resp)
        emit({"type": "phase_end", "phase": "verdict"})

    emit({"type": "session_done"})

    # Save transcript
    with open(os.path.join(session_dir, "transcript.md"), "w", encoding="utf-8") as f:
        f.write(f"# Organic Conversation Deliberation — {idea}\n\nSession: {session_id}\n")
        f.write(f"Total moves: {len(move_history)}\n\n")
        f.write("## Move History\n\n")
        for m in move_history:
            f.write(f"- R{m['round']}: {AGENTS[m['agent']]['name']} → {m['move']}\n")
        f.write(f"\n## Shared Decision Artifact\n\n{_format_artifact(artifact)}\n\n---\n\n")
        for ak, responses in all_outputs.items():
            for i, text in enumerate(responses):
                label = f" (R{i})" if len(responses) > 1 else ""
                f.write(f"## {AGENTS[ak]['name']}{label}\n\n{text}\n\n---\n\n")
    return all_outputs