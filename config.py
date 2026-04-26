"""Global configuration and model registry for the Boardroom War Game."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()  # load .env before any config variables are read

# Force OpenAI client to use Ollama Cloud base URL (CrewAI v1.x requirement)
_ollama_base = os.getenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1")
os.environ.setdefault("OPENAI_BASE_URL", _ollama_base)
os.environ.setdefault("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", os.getenv("OLLAMA_CLOUD_API_KEY", "")))


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
    "openai/kimi-k2.6:cloud": ["openai/kimi-k2.5:cloud", "openai/gemma4:31b:cloud"],
    "openai/kimi-k2.5:cloud": ["openai/gemma4:31b:cloud", "openai/gemma4:27b:cloud"],
    "openai/gemma4:31b:cloud": ["openai/gemma4:27b:cloud", "openai/kimi-k2.5:cloud"],
    "openai/gemma4:27b:cloud": ["openai/gemma4:9b:cloud", "openai/gemma4:31b:cloud"],
    "openai/gemma4:9b:cloud": ["openai/gemma4:27b:cloud", "openai/gemma4:31b:cloud"],
    "openai/glm-5.1:cloud": ["openai/gemma4:27b:cloud", "openai/gemma4:31b:cloud"],
    "openai/glm-5:cloud": ["openai/gemma4:27b:cloud", "openai/gemma4:31b:cloud"],
}

# ---------------------------------------------------------------------------
# Agent roster with personality-matched temperatures
# ---------------------------------------------------------------------------
AGENT_CONFIGS: Dict[str, AgentConfig] = {
    "board_chair": AgentConfig(
        role="Board Chair",
        model="openai/kimi-k2.6:cloud",
        fallback_chain=MODEL_REGISTRY["openai/kimi-k2.6:cloud"],
        temperature=0.3,
    ),
    "ceo": AgentConfig(
        role="CEO",
        model="openai/gemma4:31b:cloud",
        fallback_chain=MODEL_REGISTRY["openai/gemma4:31b:cloud"],
        temperature=0.7,  # Expressive
    ),
    "cfo": AgentConfig(
        role="CFO",
        model="openai/gemma4:31b:cloud",
        fallback_chain=MODEL_REGISTRY["openai/gemma4:31b:cloud"],
        temperature=0.3,
    ),
    "cto": AgentConfig(
        role="CTO",
        model="openai/glm-5.1:cloud",
        fallback_chain=MODEL_REGISTRY["openai/glm-5.1:cloud"],
        temperature=0.3,
    ),
    "cro": AgentConfig(
        role="CRO",
        model="openai/gemma4:27b:cloud",
        fallback_chain=MODEL_REGISTRY["openai/gemma4:27b:cloud"],
        temperature=0.6,  # Creative
    ),
    "customer": AgentConfig(
        role="Customer",
        model="openai/gemma4:9b:cloud",
        fallback_chain=MODEL_REGISTRY["openai/gemma4:9b:cloud"],
        temperature=0.1,  # Direct / No-fluff
    ),
    "counsel": AgentConfig(
        role="Counsel",
        model="openai/gemma4:31b:cloud",
        fallback_chain=MODEL_REGISTRY["openai/gemma4:31b:cloud"],
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
    api_key = os.getenv("OLLAMA_CLOUD_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    return {
        "model": cfg.model,
        "api_key": api_key,
        "base_url": OLLAMA_CLOUD_BASE_URL,
        "temperature": cfg.temperature,
        "max_tokens": cfg.max_tokens,
    }
