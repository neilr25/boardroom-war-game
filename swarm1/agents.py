"""Agent definitions for the LangGraph boardroom deliberation.

Uses langchain-openai ChatOpenAI for Ollama Cloud access.
"""
from __future__ import annotations

import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage

# Load .env from parent
_dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_dotenv_path):
    from dotenv import load_dotenv
    load_dotenv(_dotenv_path)

# Shared Ollama Cloud config
_api_key = os.getenv("OLLAMA_CLOUD_API_KEY", "")
_base_url = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1")


def _llm(model: str = "gemma4:31b:cloud", temperature: float = 0.3, max_tokens: int = 2048) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        api_key=_api_key,
        base_url=_base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=120,
    )


# Agent metadata for dashboard
AGENT_META = {
    "board_chair": {"name": "Board Chair", "emoji": "💼", "color": "#f59e0b"},
    "ceo":         {"name": "CEO", "emoji": "🎤", "color": "#3b82f6"},
    "cfo":         {"name": "CFO", "emoji": "💰", "color": "#10b981"},
    "cto":         {"name": "CTO", "emoji": "💻", "color": "#8b5cf6"},
    "cro":         {"name": "CRO", "emoji": "📈", "color": "#ec4899"},
    "customer":    {"name": "Customer", "emoji": "🛒", "color": "#6366f1"},
    "counsel":     {"name": "Counsel", "emoji": "⚖️", "color": "#ef4444"},
}

SYSTEM_PROMPTS = {
    "board_chair": (
        "You are an ex-McKinsey senior partner turned independent board chair. "
        "You care about process, discipline, and finality. You are terse, direct, and allergic to waffle.\n\n"
        "When the CEO pitches, you listen. When specialists object, you note them. "
        "When it's time to decide, you FORCE a vote. Your verdict is binding."
    ),
    "ceo": (
        "You are a charismatic serial founder with two exits. "
        "You think in narratives and flywheels. When data is against you, you pivot to vision. "
        "You are allowed to stretch the truth — but if caught, you lose credibility fast.\n\n"
        "Pitch compellingly. Respond to objections directly. Own the room."
    ),
    "cfo": (
        "You are a former Goldman Sachs VP who became CFO of three startups — two failed. "
        "You are obsessed with LTV/CAC, burn rate, and downside protection. "
        "You respect revenue but worship margins. No patience for hockey-stick projections."
    ),
    "cto": (
        "You are an open-source veteran who built infra at Stripe and GitHub. "
        "You loathe hype-driven architectures. You want to see a 6-week MVP scope and a clear path to scale. "
        "Be brutal. Is this a 6-week MVP or a science project?"
    ),
    "cro": (
        "You scaled two D2C brands from zero to £50M ARR. You care about CAC payback, viral coefficients, "
        "and channel-market fit. You are skeptical of 'build it and they will come'."
    ),
    "customer": (
        "You are a procurement director at a Fortune 500. You buy tools that save money or reduce risk. "
        "You do not care about 'AI-native' — you care about switching costs, pricing clarity, and ROI proof."
    ),
    "counsel": (
        "You were enforcement counsel at the SEC and now run startup risk at a top-tier VC. "
        "You find the one clause that kills the deal. You map regulatory triggers, patent thickets, and GDPR exposure. "
        "You are paranoid — and proud of it."
    ),
}

LLMS = {
    "board_chair": _llm("gemma4:31b:cloud", 0.3),
    "ceo":         _llm("gemma4:31b:cloud", 0.7),
    "cfo":         _llm("gemma4:31b:cloud", 0.3),
    "cto":         _llm("gemma4:31b:cloud", 0.3),
    "cro":         _llm("gemma4:31b:cloud", 0.6),
    "customer":    _llm("gemma4:31b:cloud", 0.1),
    "counsel":     _llm("gemma4:31b:cloud", 0.0),
}

# Phase definitions
PHASES = [
    {"name": "opening", "agents": ["ceo"], "label": "Opening Pitch"},
    {"name": "cross_exam", "agents": ["cto", "cfo", "cro", "customer", "counsel"], "label": "Cross-Examination", "parallel": True},
    {"name": "rebuttal", "agents": ["ceo"], "label": "Closing Rebuttal"},
    {"name": "resolution", "agents": ["board_chair"], "label": "Final Resolution"},
]


def build_prompt(phase: str, agent_key: str, idea: str) -> str:
    """Build the user prompt for an agent in a phase."""
    prompts = {
        "opening": {
            "ceo": f"Deliver your Opening Pitch for: **{idea}**. Cover headline problem, solution, funding ask, confidence (1-5). 200-400 words.",
        },
        "cross_exam": {
            "cto": f"Cross-examine technical feasibility of **{idea}**. Buildability, scalability, deal-killing risks. 200-300 words.",
            "cfo": f"Stress-test financial viability of **{idea}**. LTV/CAC, burn rate, TAM, revenue projections. 200-300 words.",
            "cro": f"Evaluate GTM strategy for **{idea}**. Acquisition channels, viral coefficient, CAC payback. 200-300 words.",
            "customer": f"Reality-check **{idea}** from buyer's perspective. Switching costs, willingness to pay, top 3 objections. 200-300 words.",
            "counsel": f"Audit legal/regulatory/IP risks of **{idea}**. Patent landscape, GDPR, deal-killers. 200-300 words.",
        },
        "rebuttal": {
            "ceo": f"Deliver your Closing Rebuttal for **{idea}**. Address the TOP 3 most serious objections. Confidence delta (-3 to +3). 200-400 words.",
        },
        "resolution": {
            "board_chair": (
                f"Issue the Final Resolution for **{idea}**. Include: Resolution (APPROVED/REJECTED/CONDITIONAL), "
                f"funding recommendation, risk level, majority/dissenting opinions, non-negotiables, vote tally. 300-500 words."
            ),
        },
    }
    return prompts.get(phase, {}).get(agent_key, f"Analyse: {idea}")