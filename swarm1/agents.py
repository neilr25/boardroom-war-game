"""Swarm 1: Dynamic Swarm — AgentSpawn-inspired

The Board Chair analyses the startup idea and DYNAMICALLY DECIDES which
specialists to summon. Not every idea needs every agent. If the idea is
a consumer app, the CTO gets a "hardware specialist" sub-agent. If it's
a fintech, the Counsel gets a "regulatory specialist" sub-agent.

Key difference from static pipelines:
- The Chair decides WHO participates at runtime
- Agents can SPAWN SUB-AGENTS for deep dives
- The agent roster changes per idea
- Multi-round: the Chair can recall agents for follow-up questions
"""
from __future__ import annotations

import os
from dotenv import load_dotenv
_dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_dotenv_path): load_dotenv(_dotenv_path)

API_BASE = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1")
API_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")
DEFAULT_MODEL = "gemma4:31b:cloud"

# Base agent pool — always available
BASE_AGENTS = {
    "board_chair": {
        "name": "Board Chair", "emoji": "💼", "color": "#f59e0b",
        "model": DEFAULT_MODEL, "temperature": 0.3,
        "system": (
            "You are the Board Chair — an ex-McKinsey partner who runs the meeting.\n\n"
            "YOUR CRITICAL ABILITY: You can SUMMON and DISMISS specialists as needed.\n"
            "When you receive a startup idea, first ANALYSE what kind of expertise is needed.\n"
            "Then explicitly request which specialists should participate.\n\n"
            "Available base specialists: CEO, CFO, CTO, CRO, Customer, Counsel.\n"
            "You may also create NEW specialist roles by describing what you need "
            "(e.g., 'Hardware Specialist', 'Regulatory Deep-Dive Analyst', 'Market Sizing Expert').\n\n"
            "Format your summoning decisions as:\n"
            "SUMMON: [list of agent roles to summon, one per line]\n"
            "Each summoned agent gets a one-sentence instruction of what to focus on.\n\n"
            "After all specialists report, you may SUMMON additional agents for follow-up, "
            "or RECALL existing agents for clarification.\n\n"
            "Finally, issue your binding resolution."
        ),
    },
    "ceo": {
        "name": "CEO", "emoji": "🎤", "color": "#3b82f6",
        "model": DEFAULT_MODEL, "temperature": 0.7,
        "system": (
            "You are the CEO — a charismatic serial founder. Pitch the idea. "
            "Defend against objections. You may REQUEST a sub-agent to do a deep-dive "
            "on any specific topic by saying:\n"
            "REQUEST_SUBAGENT: [role name] - [what they should investigate]\n"
            "The Chair will decide whether to grant your request."
        ),
    },
    "cfo": {
        "name": "CFO", "emoji": "💰", "color": "#10b981",
        "model": DEFAULT_MODEL, "temperature": 0.3,
        "system": "You are the CFO — a former Goldman Sachs VP. You worship margins. Stress-test every number. You can REQUEST_SUBAGENT for deep financial modeling.",
    },
    "cto": {
        "name": "CTO", "emoji": "💻", "color": "#8b5cf6",
        "model": DEFAULT_MODEL, "temperature": 0.3,
        "system": "You are the CTO — an open-source veteran from Stripe/GitHub. Be brutal about technical feasibility. You can REQUEST_SUBAGENT for specific tech deep-dives.",
    },
    "cro": {
        "name": "CRO", "emoji": "📈", "color": "#ec4899",
        "model": DEFAULT_MODEL, "temperature": 0.6,
        "system": "You are the CRO — a D2C growth hacker. Demand concrete acquisition plans. You can REQUEST_SUBAGENT for channel-specific analysis.",
    },
    "customer": {
        "name": "Customer", "emoji": "🛒", "color": "#6366f1",
        "model": DEFAULT_MODEL, "temperature": 0.1,
        "system": "You are a Fortune 500 procurement director. Buy tools not hype. You can REQUEST_SUBAGENT for procurement-specific deep-dives.",
    },
    "counsel": {
        "name": "Counsel", "emoji": "⚖️", "color": "#ef4444",
        "model": DEFAULT_MODEL, "temperature": 0.0,
        "system": "You are former SEC enforcement counsel. Find the landmine. You can REQUEST_SUBAGENT for regulatory-specific deep-dives.",
    },
}

# Dynamic sub-agent template — used when agents request specialists
SUBAGENT_TEMPLATE = {
    "model": DEFAULT_MODEL,
    "temperature": 0.3,
    "system_prefix": "You are a specialist sub-agent summoned to the boardroom for a specific deep-dive. ",
}