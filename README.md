# Boardroom War Game

A multi-agent startup stress-test simulation using CrewAI. Seven AI board members, each running a distinct Ollama Cloud model, debate and vote on your startup idea.

## Quick Start

```bash
cd C:\Projects\crewai\boardroom
cp .env.example .env
# Edit .env with your OLLAMA_CLOUD_API_KEY

# Dry run (prints roster, no API calls)
python main.py --idea "AI-powered toothbrushes" --dry-run

# Single-round evaluation (live API calls)
python main.py --idea "AI-powered toothbrushes"

# Multi-round with custom session ID
python main.py --idea "AI-powered toothbrushes" --rounds 3 --session-id ideathon-2026

# Mock mode (no API calls, deterministic placeholders)
python main.py --idea "AI-powered toothbrushes" --mock
```

## Architecture

- **Agents** (`agents.py`): 7 board members with diverse models and personalities
- **Tasks** (`tasks.py`): 8 tasks with Pydantic output schemas and rubrics
- **Models** (`models.py`): Output types for every task + final resolution
- **Tools** (`tools.py`): Calculator, file I/O, web search stub
- **Callbacks** (`callbacks.py`): Dramatic transcript logging
- **File I/O** (`file_io.py`): Session persistence (transcript, memos, resolution)
- **Config** (`config.py`): Model registry, temperature mapping, fallback chains
- **Main** (`main.py`): CLI, crew assembly, round orchestration, signal handling

## Board Roster

| Role | Model | Temperature | Personality |
|------|-------|-------------|------------|
| Board Chair | `kimi-k2.6:cloud` | 0.3 | Ex-McKinsey orchestrator |
| CEO | `gemma4:31b:cloud` | 0.7 | Charismatic visionary |
| CFO | `deepseek-v4-pro:cloud` | 0.3 | Goldman Sachs risk-auditor |
| CTO | `glm-5.1:cloud` | 0.3 | Open-source builder |
| CRO | `gemma4:27b:cloud` | 0.6 | Creative D2C growth hacker |
| Customer | `gemma4:9b:cloud` | 0.1 | Pragmatic buyer |
| Counsel | `deepseek-v4-pro:cloud` | 0.0 | Paranoid former SEC counsel |

## Workflow

Opening Pitch (CEO)
  → [Parallel] Technical Cross-Exam (CTO)
  → [Parallel] Financial Stress-Test (CFO)
  → [Parallel] GTM Analysis (CRO)
  → [Parallel] Customer Reality Check (Customer)
  → [Parallel] Risk Audit (Counsel)
  → Closing Rebuttal (CEO)
  → Final Resolution (Board Chair)

## Output

```text
./boardroom/<session_id>/
  ├── transcript.md    # Dramatic board meeting log
  ├── memos/
  │   ├── opening-pitch.md
  │   ├── technical-cross-exam.md
  │   ├── financial-stress-test.md
  │   ├── gtm-analysis.md
  │   ├── customer-reality-check.md
  │   ├── risk-audit.md
  │   ├── closing-rebuttal.md
  │   └── final-resolution.md
  └── RESOLUTION.md   # YAML frontmatter + final decision

## Decisions

- **CrewAI v1.x** HierarchicalProcess with manager agent (Board Chair)
- **Diverse models retained** per user explicit request for emergent conflict
- **Parallel tasks** for CTO/CFO/CRO/Customer/Counsel after Opening Pitch
- **Pydantic outputs** for structured memos and guaranteed RESOLUTION.md validity
- **Model registry** with deterministic fallback chains in config.py
- **Filesystem-only persistence** (no n8n integration per user request)
- **max_rpm: 20** at Crew level for Ollama Cloud rate limit compliance
- **Graceful KeyboardInterrupt** saves snapshot.json before exit
```
