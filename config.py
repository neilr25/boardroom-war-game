"""Global configuration and model registry for the Boardroom War Game."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class AgentConfig:
    """Per-agent configuration."""
    role: str
    model: str
    fallback_chain: List[str] = field(default_factory=list)
    temperature: float = 0.3
    max_tokens: int = 4096
    max_rpm: int = 20


# ---------------------------------------------------------------------------
# Model registry — deterministic fallback chains
# ---------------------------------------------------------------------------
MODEL_REGISTRY: Dict[str, List[str]] = {
    # Primary model: fallback chain (nearest available first)
    "kimi-k2.6:cloud": ["kimi-k2.5:cloud", "gemma4:31b:cloud"],
    "gemma4:31b:cloud": ["gemma4:27b:cloud", "deepseek-v4:cloud"],
    "deepseek-v4-pro:cloud": ["deepseek-v4:cloud", "deepseek-v4-flash:cloud"],
    "glm-5.1:cloud": ["glm-5:cloud", "gemma4:27b:cloud"],
    "gemma4:27b:cloud": ["gemma4:9b:cloud", "deepseek-v4-flash:cloud"],
    "gemma4:9b:cloud": ["gemma4:4b:cloud", "deepseek-v4-flash:cloud"],
}

# ---------------------------------------------------------------------------
# Agent roster with personality-matched temperatures
# ---------------------------------------------------------------------------
AGENT_CONFIGS: Dict[str, AgentConfig] = {
    "board_chair": AgentConfig(
        role="Board Chair",
        model="kimi-k2.6:cloud",
        fallback_chain=MODEL_REGISTRY["kimi-k2.6:cloud"],
        temperature=0.3,
    ),
    "ceo": AgentConfig(
        role="CEO",
        model="gemma4:31b:cloud",
        fallback_chain=MODEL_REGISTRY["gemma4:31b:cloud"],
        temperature=0.7,  # Expressive → can be overridden mid-flow if API supports
    ),
    "cfo": AgentConfig(
        role="CFO",
        model="deepseek-v4-pro:cloud",
        fallback_chain=MODEL_REGISTRY["deepseek-v4-pro:cloud"],
        temperature=0.3,
    ),
    "cto": AgentConfig(
        role="CTO",
        model="glm-5.1:cloud",
        fallback_chain=MODEL_REGISTRY["glm-5.1:cloud"],
        temperature=0.3,
    ),
    "cro": AgentConfig(
        role="CRO",
        model="gemma4:27b:cloud",
        fallback_chain=MODEL_REGISTRY["gemma4:27b:cloud"],
        temperature=0.6,  # Creative
    ),
    "customer": AgentConfig(
        role="Customer",
        model="gemma4:9b:cloud",
        fallback_chain=MODEL_REGISTRY["gemma4:9b:cloud"],
        temperature=0.1,  # Direct / No-fluff
    ),
    "counsel": AgentConfig(
        role="Counsel",
        model="deepseek-v4-pro:cloud",
        fallback_chain=MODEL_REGISTRY["deepseek-v4-pro:cloud"],
        temperature=0.0,  # Pro-Max — analytical, no hallucination
        max_tokens=8192,
    ),
}

# ---------------------------------------------------------------------------
# Global settings
# ---------------------------------------------------------------------------

OLLAMA_CLOUD_API_KEY = os.getenv("OLLAMA_CLOUD_API_KEY", "")
OLLAMA_CLOUD_BASE_URL = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1")
MAX_RPM = int(os.getenv("MAX_RPM", "20"))
BOARDROOM_OUTPUT_DIR = os.getenv("BOARDROOM_OUTPUT_DIR", "./boardroom")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_llm_config(agent_key: str) -> Dict:
    """Return a dict ready for CrewAI LLM constructor."""
    cfg = AGENT_CONFIGS[agent_key]
    return {
        "model": cfg.model,
        "api_key": OLLAMA_CLOUD_API_KEY,
        "base_url": OLLAMA_CLOUD_BASE_URL,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
