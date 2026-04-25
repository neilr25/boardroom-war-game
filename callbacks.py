"""Dramatic callbacks for the boardroom simulation.

Every task callback writes a theatrical transcript entry, so the session
reads like a screenplay of a tense board meeting.
"""

from __future__ import annotations

from typing import Any, Optional

from file_io import SessionWriter


class TranscriptLogger:
    """Captures dramatic boardroom events to transcript.md."""

    def __init__(self, writer: SessionWriter):
        self.writer = writer
        self._round = 0

    # ------------------------------------------------------------------
    # Lifecycle events
    # ------------------------------------------------------------------

    def on_session_start(self, rounds: int) -> None:
        self.writer.append_to_transcript(
            '🎬 **THE BOARD IS CALLED TO ORDER.**\n\n'
            f'Agenda: Evaluate the proposal. Deliberation cycles: {rounds}.\n'
            'Chair: *"Ladies and gentlemen, we have a new pitch on the table."*'
        )

    def on_round_start(self, round_num: int) -> None:
        self._round = round_num
        self.writer.append_to_transcript(
            f'\n---\n\n📋 **ROUND {round_num}**\n\n'
            f'Chair: *"Let\'s begin round {round_num}."*'
        )

    def on_round_end(self, round_num: int) -> None:
        self.writer.append_to_transcript(
            f'\n⏳ **ROUND {round_num} CONCLUDES.**\n\n'
            'Chair: *"We will reconvene for final arguments."*'
        )

    # ------------------------------------------------------------------
    # Task-level drama
    # ------------------------------------------------------------------

    def on_task_start(self, agent: str, task_name: str) -> None:
        self.writer.append_to_transcript(
            f'\n🗣️ **{agent}** stands to deliver *{task_name}*...'
        )

    def on_task_end(self, agent: str, task_name: str, output: Any) -> None:
        # Try to extract a brief headline from structured output
        headline = ""
        if hasattr(output, "headline"):
            headline = f' — *{output.headline}*'
        elif isinstance(output, str) and len(output) < 120:
            headline = f' — *{output}*'

        self.writer.append_to_transcript(
            f'✅ **{agent}** concludes *{task_name}*{headline}'
        )

    def on_task_retry(self, agent: str, task_name: str, attempt: int) -> None:
        self.writer.append_to_transcript(
            f'⚠️ **{agent}** stumbles on *{task_name}* (attempt {attempt}). The board waits...'
        )

    # ------------------------------------------------------------------
    # Model fallback
    # ------------------------------------------------------------------

    def on_model_fallback(
        self, agent: str, failed_model: str, fallback_model: str, error: Optional[str] = None
    ) -> None:
        msg = (
            f'🔧 **{agent}**\'s primary model `{failed_model}` is unavailable. '
            f'Falling back to `{fallback_model}`.'
        )
        if error:
            msg += f' *(Reason: {error})*'
        self.writer.append_to_transcript(msg)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def on_resolution(self, resolution: str, risk_level: str) -> None:
        emoji = {"APPROVED": "✅", "REJECTED": "❌", "CONDITIONAL": "⚡"}.get(
            resolution, "❓"
        )
        self.writer.append_to_transcript(
            f'\n🏛️ **FINAL VOTE**\n\n'
            f'Chair: *"The board has reached a decision."*\n\n'
            f'{emoji} **{resolution}** — Risk Level: {risk_level}'
        )

    # ------------------------------------------------------------------
    # Interruption
    # ------------------------------------------------------------------

    def on_interrupt(self) -> None:
        self.writer.append_to_transcript(
            '\n🚪 **SESSION INTERRUPTED.**\n\n'
            'Chair: *"We are adjourned. The clerk will preserve the record."*'
        )

    def on_session_end(self) -> None:
        self.writer.append_to_transcript(
            '\n🏛️ **SESSION ADJOURNED.**\n\n'
            'Chair: *"The record is sealed. Good evening, everyone."*'
        )
