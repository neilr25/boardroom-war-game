Here is the complete, professional specification for your **Boardroom War Game**. I have structured this as a technical requirements document so that you can save it as a `.md` file and feed it directly to OpenCode (or any agent) as the "Source of Truth" for the build.

***

# Specification: Boardroom War Game (Multi-Agent Simulation)

## 1. Project Overview
The **Boardroom War Game** is an experimental multi-agent simulation designed to stress-test startup ideas through a simulated corporate board meeting. Using a **hierarchical orchestration** pattern, a Board Chair manages a team of specialized executives who debate, critique, and ultimately vote on whether to fund a user-provided business concept.

### Core Objectives
- **Emergent Conflict:** Agents should not simply agree; they must operate based on conflicting incentives (e.g., the CEO wants valuation, the CFO wants risk mitigation).
- **High-Fidelity Reasoning:** Leverage the latest April 2026 model releases to simulate deep strategic thinking and technical auditing.
- **Auditability:** Every "argument" and "memo" must be persisted to disk for post-game analysis.

---

## 2. Technical Architecture

### Framework & Infrastructure
- **Orchestration:** `CrewAI` (Hierarchical Process)
- **Inference:** Ollama Cloud API (Remote)
- **Pattern:** Based on `bhancockio/crewai-updated-tutorial-hierarchical` (Async tasks, callbacks, and expected outputs).
- **State Management:** `memory=True` and `planning=True` to ensure the Board Chair creates a formal agenda and agents remember previous objections.

### Project Structure
```text
/boardroom-war-game
├── main.py            # CLI Entry point & Crew assembly
├── config.py          # Ollama Cloud API & Model mapping
├── agents.py          # Agent definitions (Roles, Backstories, LLMs)
├── tasks.py           # Task definitions (Rubrics, Dependencies, Callbacks)
├── tools.py           # Custom tools (Web Search, File I/O, Calculator)
├── callbacks.py      # Dramatic event logging & transcript management
├── file_io.py         # Async filesystem utilities
├── requirements.txt   # Dependencies (crewai, langchain-community, etc.)
└── .env.example       # API Keys and Model overrides
```

---

## 3. The Board (Agent Roster)

| Role | Model (Ollama Cloud) | Personality & Incentive | Reasoning Mode |
| :--- | :--- | :--- | :--- |
| **Board Chair** | `kimi-k2.6:cloud` | **The Orchestrator.** Ex-McKinsey. Focuses on process, discipline, and finality. | Standard |
| **CEO** | `gemma4:31b:cloud` | **The Visionary.** Charismatic, narrative-driven, deflects hard data with "vision." | Expressive $\rightarrow$ Analytical |
| **CFO** | `deepseek-v4-pro:cloud` | **The Killer.** Former Goldman Sachs. Obsessed with LTV/CAC and burn rate. | Standard |
| **CTO** | `glm-5.1:cloud` | **The Builder.** Open-source veteran. Hates hype; demands a 6-week MVP scope. | Standard |
| **CRO** | `gemma4:27b:cloud` | **The Hustler.** D2C growth expert. Cares about viral loops and conversion. | Creative |
| **Customer** | `gemma4:9b:cloud` | **The Pragmatist.** Voice of the buyer. Asks "Who actually pays for this?" | Direct / No-fluff |
| **Counsel** | `deepseek-v4-pro:cloud` | **The Risk Officer.** Ex-SEC. Finds the regulatory/IP landmines. | **Pro-Max Reasoning** |

---

## 4. The Simulation Workflow (Task Sequence)

All tasks must include a **rubric** in the `expected_output` and a **dramatic callback** for the logs.

1. **Opening Pitch** $\rightarrow$ *CEO* $\rightarrow$ (Problem, Solution, The Ask).
2. **Technical Cross-Exam** $\rightarrow$ *CTO* $\rightarrow$ (Buildability, Scalability, MVP Scope).
3. **Financial Stress-Test** $\rightarrow$ *CFO* $\rightarrow$ (Unit Economics, TAM, Red Flags).
4. **GTM Analysis** $\rightarrow$ *CRO* $\rightarrow$ (Acquisition Channels, Viral Coefficient).
5. **Customer Reality Check** $\rightarrow$ *Customer* $\rightarrow$ (Switching Costs, JTBD Analysis).
6. **Risk Audit** $\rightarrow$ *Counsel* $\rightarrow$ (Regulatory/IP Matrix, Deal-killers).
7. **Closing Rebuttal** $\rightarrow$ *CEO* $\rightarrow$ (Addressing the top 3 board objections).
8. **Final Resolution** $\rightarrow$ *Chair* $\rightarrow$ (Synthesizes all memos $\rightarrow$ Forces Vote $\rightarrow$ Resolution).

---

## 5. Output Requirements

### File System Artifacts
Every session must generate a unique folder: `./boardroom/<session_id>/`
- `transcript.md`: A running log of the "drama" (via callbacks).
- `memos/*.md`: Individual output files for each of the 8 tasks.
- `RESOLUTION.md`: The final decision with YAML frontmatter:
  ```yaml
  resolution: [APPROVED | REJECTED | CONDITIONAL]
  funding_recommendation: £X
  risk_level: [LOW | MEDIUM | HIGH | EXISTENTIAL]
  majority_opinion: "..."
  dissenting_opinion: "..."
  non_negotiables: [list]
  ```

### CLI Interface
- `python main.py --idea "Your Idea Here"`
- `--dry-run`: Print the board roster and model assignments without executing.
- `--rounds 1`: Number of deliberation cycles.

---

## 6. Implementation Notes for OpenCode
- **Rate Limiting:** Implement `max_rpm: 20` to avoid Ollama Cloud throttling.
- **Graceful Exit:** Handle `KeyboardInterrupt` by saving the current state of the transcript and any completed memos.
- **Model Fallbacks:** If a specific `:cloud` tag is unavailable, the system should fallback to the nearest available version (e.g., `deepseek-v3:cloud`) and log a warning.
- **Memory:** Ensure `memory=True` is enabled so the CFO remembers the CEO's lie from Task 1 during the Final Vote.