"""Boardroom War Game — CLI entry point.

Usage:
    python main.py --idea "Your startup idea here"
    python main.py --idea "Idea" --dry-run
    python main.py --idea "Idea" --rounds 3 --session-id my-session
    python main.py --idea "Idea" --mock
"""

from __future__ import annotations

import argparse
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from crewai import Crew, LLM, Process
from dotenv import load_dotenv

from agents import build_agents
from callbacks import TranscriptLogger
from config import OLLAMA_CLOUD_API_KEY, OLLAMA_CLOUD_BASE_URL, get_llm_config
from file_io import SessionWriter
from tasks import build_tasks

# Load .env before any config is read
load_dotenv()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Boardroom War Game — Multi-Agent Startup Stress Test"
    )
    parser.add_argument(
        "--idea",
        required=True,
        help="The startup idea to evaluate",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Number of deliberation cycles (default: 1)",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Custom session ID (default: auto-generated UUID)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the board roster and exit without executing",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock LLM responses for testing (no API calls)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Dry-run roster printer
# ---------------------------------------------------------------------------

def _dry_run(agents: dict[str, Any]) -> None:
    print("\n[BOARDROOM] BOARDROOM WAR GAME -- Dry Run\n")
    print(f"{'Role':<15} {'Model':<30} {'Temp'}")
    print("-" * 60)
    for key, agent in agents.items():
        temp = getattr(agent.llm, "temperature", "--")
        print(f"{agent.role:<15} {agent.llm.model:<30} {temp}")
    print("\nNo API calls made. To execute, drop --dry-run.\n")


# ---------------------------------------------------------------------------
# Round runner
# ---------------------------------------------------------------------------

def _run_round(
    round_num: int,
    idea: str,
    agents: dict,
    logger: TranscriptLogger,
    writer: SessionWriter,
    mock: bool = False,
) -> Any:
    """Execute a single deliberation round."""

    logger.on_round_start(round_num)

    # Build task graph for this round
    tasks = build_tasks(agents, idea)

    # In mock mode we bypass the Crew and return deterministic canned responses.
    if mock:
        print(f"[MOCK] Round {round_num} — returning canned outputs")
        # We still write placeholder memos so the pipeline is testable.
        for t in tasks:
            output = t.output_pydantic.model_construct() if t.output_pydantic else "MOCK"
            writer.write_memo(t.description.split("\n")[0], t.agent.role, str(output))
        logger.on_round_end(round_num)
        return "MOCK"

    # Assemble the crew and run
    # Separate manager from agents list to avoid mutation across rounds
    manager = agents["board_chair"]
    crew_agents = [v for k, v in agents.items() if k != "board_chair"]
    # Force env vars before Crew init to prevent defaulting to OpenAI
    import os
    os.environ["OPENAI_API_KEY"] = OLLAMA_CLOUD_API_KEY or os.getenv("OPENAI_API_KEY", "")
    os.environ["OPENAI_BASE_URL"] = OLLAMA_CLOUD_BASE_URL

    manager_llm = LLM(**get_llm_config("board_chair"))
    crew = Crew(
        agents=crew_agents,
        tasks=tasks,
        process=Process.hierarchical,
        manager_agent=manager,
        manager_llm=manager_llm,
        verbose=True,
        planning=False,
    )

    result = crew.kickoff(inputs={"idea": idea})

    logger.on_round_end(round_num)
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = _cli()

    # API key check (skip for dry-run)
    if not args.dry_run and not args.mock and not OLLAMA_CLOUD_API_KEY:
        print(
            "Error: OLLAMA_CLOUD_API_KEY not set.\n"
            "Copy .env.example to .env and fill in your key."
        )
        return 1

    # Session identity
    session_id = args.session_id or f"session-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    print(f"Session ID: {session_id}")

    # Build agents
    agents = build_agents()

    # Dry run prints roster and exits
    if args.dry_run:
        _dry_run(agents)
        return 0

    # Persistence + logging
    writer = SessionWriter(session_id, args.idea)
    logger = TranscriptLogger(writer)

    # Graceful interrupt handler
    completed_rounds: List[int] = []

    def _signal_handler(sig: int, frame) -> None:
        print("\n\n[!] Interrupted by user.")
        logger.on_interrupt()
        writer.snapshot_state(
            completed_tasks=[f"round_{r}" for r in completed_rounds]
        )
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Session start
    logger.on_session_start(args.rounds)

    # Run rounds
    for r in range(1, args.rounds + 1):
        _run_round(r, args.idea, agents, logger, writer, mock=args.mock)
        completed_rounds.append(r)

    logger.on_session_end()
    print(f"\n[OK] Session complete. Artifacts written to: {writer.root}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as e:
        sys.exit(e.code)
