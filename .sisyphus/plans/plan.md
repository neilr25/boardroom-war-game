# Boardroom War Game — Implementation Plan

*Decisions recorded for unattended overnight development*

## Decisions Made

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | **CrewAI v1.x** (latest) | `memory=True`/`planning=True` are v0.x flags; v1.x uses explicit memory objects and `HierarchicalProcess` naturally plans. |
| 2 | **Standalone CLI**, no n8n | Spec is an experimental simulation; filesystem persistence is sufficient. No n8n integration needed. |
| 3 | **Diverse models retained** (kimi-k2.6, gemma4:31b, deepseek-v4-pro, glm-5.1, gemma4:27b, gemma4:9b) | User explicitly requested diversity to create emergent conflict. |
| 4 | **Filesystem-only persistence** | Session dir with transcript.md, memos/*.md, RESOLUTION.md. No n8n Data Tables. |
| 5 | **Parallel workflow** | Opening Pitch → [CTO+CFO+CRO+Customer+Counsel parallel] → Closing Rebuttal → Final Resolution. Cuts latency from ~8 serial calls to ~4 batches. |
| 6 | **Pydantic output schemas per task** | Guarantees structured memos and valid RESOLUTION.md YAML frontmatter. |
| 7 | **Model registry with deterministic fallback chain** | `kimi-k2.6:cloud` → `gemma4:31b:cloud` → `deepseek-v4:cloud` for Chair; per-agent chains in config. |
| 8 | **Temperature mapping for "reasoning modes"** | Expressive=0.7, Standard=0.3, Creative=0.6, Direct=0.1, Pro-Max=0.0+CoT prompt. |
| 9 | **Docker + docker-compose** | Included per user "if possible". Uses python:3.11-slim, mounts local `./boardroom` for persistence. |
| 10 | **max_rpm: 20** per spec | Applied at Crew level to respect Ollama Cloud rate limits. |
| 11 | **Round behavior (N>1)** | Skip opening pitch after round 1. Re-run parallel tasks with full context of previous objections. CEO rebuttal addresses top 3 from all rounds. Chair synthesizes across all rounds. |
| 12 | **Mock-LLM harness** | `--mock` mode with deterministic canned responses per role. Enables CI and rapid prompt iteration without burning tokens. |

## Task Breakdown

### Phase 1: Scaffold (0%)
- requirements.txt
- Dockerfile, docker-compose.yml
- .env.example
- config.py (Pydantic settings, model registry, temperature mapping)

### Phase 2: Utilities (0%)
- file_io.py (session dir, memo writer, transcript, resolution)
- callbacks.py (dramatic logging, transcript events, progress tracking)
- tools.py (CalculatorTool, FileIOTool, WebSearch stub)

### Phase 3: Core (0%)
- models.py (Pydantic output schemas for all 8 tasks + resolution)
- agents.py (7 agents with roles, backstories, diverse models, fallbacks)
- tasks.py (8 tasks with rubrics, parallel groupings, pydantic outputs)
- main.py (CLI, crew assembly, hierarchical process, signal handling, rounds)

### Phase 4: Validation (0%)
- py_compile all modules
- dry-run test
- mock-LLM test
- README.md with usage instructions

### Phase 5: Delivery (0%)
- git commit
- Push to GitHub (remote TBD — record if not available)

## Known Risks
- CrewAI v1.x HierarchicalProcess with diverse LLM backends is bleeding-edge; may need workaround if per-agent LLM assignment is buggy.
- Ollama Cloud model availability for all 7 models is assumed but untested at 2026-04-25.
- Fallback chain needs live validation.

## Progress Log
- 2026-04-25 21:35 — Plan initialized. Git repo initialized.
