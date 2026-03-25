"""
services/orchestration/context_loader/prompt_loader.py

Loads prompt templates from the prompts/ folder.
Prompts are externalized so they can be iterated without code changes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# In Docker: /app/prompts (volume mount)
# Locally: pmm-ai-agent/prompts/ (3 levels up from this file)
_APP_DIR = Path(__file__).parents[1]  # /app or services/orchestration
PROMPTS_DIR = _APP_DIR / "prompts" if (_APP_DIR / "prompts").exists() else Path(__file__).parents[3] / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Load a prompt template by name (without .txt extension).
    Cached indefinitely — prompts only change with code deploys.

    Usage:
        prompt = load_prompt("entry_node")
        formatted = prompt.format(pm_name="Prasanth", pm_products="AIA, ECAI")
    """
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")
