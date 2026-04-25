"""Filesystem persistence for boardroom sessions.

Every session generates a unique folder under BOARDROOM_OUTPUT_DIR:
    ./boardroom/<session_id>/
        transcript.md
        memos/<task_name>.md
        RESOLUTION.md
"""

from __future__ import annotations

import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from config import BOARDROOM_OUTPUT_DIR


class SessionWriter:
    """Handles all disk I/O for a single simulation session."""

    def __init__(self, session_id: str, idea: str):
        self.session_id = session_id
        self.idea = idea
        self.root = Path(BOARDROOM_OUTPUT_DIR) / session_id
        self.memos_dir = self.root / "memos"
        self.transcript_path = self.root / "transcript.md"
        self.resolution_path = self.root / "RESOLUTION.md"

        # Ensure directories exist
        self.memos_dir.mkdir(parents=True, exist_ok=True)
        self._init_transcript()

    # ------------------------------------------------------------------
    # Transcript (markdown log of drama)
    # ------------------------------------------------------------------

    def _init_transcript(self) -> None:
        """Create transcript.md with YAML frontmatter header."""
        header = textwrap.dedent(
            f"""\
            ---
            session_id: {self.session_id}
            idea: "{self.idea}"
            started_at: {datetime.now(timezone.utc).isoformat()}"
            ---

            # Boardroom War Game — Transcript

            """
        )
        self.transcript_path.write_text(header, encoding="utf-8")

    def append_to_transcript(self, entry: str) -> None:
        """Append a dramatic log entry with timestamp."""
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        line = f"**[{now}]** {entry}\n\n"
        with self.transcript_path.open("a", encoding="utf-8") as f:
            f.write(line)

    # ------------------------------------------------------------------
    # Memos (individual task outputs)
    # ------------------------------------------------------------------

    def write_memo(self, task_slug: str, agent: str, content: str) -> None:
        """Persist a task output as a markdown memo file."""
        safe_name = re.sub(r"[^a-z0-9_-]+", "-", task_slug.lower())[:60].strip("-")
        memo_path = self.memos_dir / f"{safe_name}.md"
        header = textwrap.dedent(
            f"""\
            ---
            task: "{task_slug}"
            agent: "{agent}"
            timestamp: {datetime.now(timezone.utc).isoformat()}"
            ---

            {content}

            """
        )
        memo_path.write_text(header, encoding="utf-8")

    # ------------------------------------------------------------------
    # Resolution (final YAML-frontmatter document)
    # ------------------------------------------------------------------

    def write_resolution(
        self,
        resolution: str,
        funding_recommendation: str,
        risk_level: str,
        majority_opinion: str,
        dissenting_opinion: str,
        non_negotiables: List[str],
        round_summaries: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Write the final RESOLUTION.md with YAML frontmatter + narrative."""
        frontmatter = {
            "session_id": self.session_id,
            "resolution": resolution,
            "funding_recommendation": funding_recommendation,
            "risk_level": risk_level,
            "majority_opinion": majority_opinion,
            "dissenting_opinion": dissenting_opinion,
            "non_negotiables": non_negotiables or [],
        }
        if round_summaries:
            frontmatter["rounds"] = round_summaries

        body = textwrap.dedent(
            f"""\
            # Final Resolution — {self.session_id}

            **Idea:** {self.idea}

            **Decision:** {resolution}
            **Risk Level:** {risk_level}
            **Funding Recommendation:** {funding_recommendation}

            ## Majority Opinion
            {majority_opinion}

            ## Dissenting Opinion
            {dissenting_opinion}

            ## Non-Negotiables
            {chr(10).join(f"- {item}" for item in (non_negotiables or []))}

            ---

            *Session completed at {datetime.now(timezone.utc).isoformat()}"
            """
        )

        content = "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n\n" + body
        self.resolution_path.write_text(content, encoding="utf-8")

    # ------------------------------------------------------------------
    # Snapshot (for KeyboardInterrupt recovery)
    # ------------------------------------------------------------------

    def snapshot_state(self, completed_tasks: List[str]) -> None:
        """Write a lightweight snapshot of completed tasks for resume."""
        snapshot = {
            "session_id": self.session_id,
            "idea": self.idea,
            "completed_tasks": completed_tasks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        snapshot_path = self.root / "SNAPSHOT.json"
        import json

        snapshot_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
