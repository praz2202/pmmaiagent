"""
services/orchestration/context_loader/skill_loader.py

Loads SKILL.md and references/ files from skill folders.
Skills live in the repo — loaded once at process start, cached forever.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# In Docker: /app/config/skills (volume mount)
# Locally: 3 levels up from this file
_APP_DIR = Path(__file__).parents[1]
SKILLS_DIR = _APP_DIR / "config" / "skills" if (_APP_DIR / "config" / "skills").exists() else Path(__file__).parents[3] / "config" / "skills"


@lru_cache(maxsize=None)
def load_skill_md(skill_name: str) -> str:
    """Load SKILL.md for a named skill (e.g. 'aha', 'egain').
    Cached indefinitely — skills only change with code deploys.
    """
    path = SKILLS_DIR / skill_name / "SKILL.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_skill_reference(skill_name: str, filename: str) -> str:
    """Load a references/ file lazily — only when the agent needs it.
    NOT cached — these are large and only needed occasionally.
    """
    path = SKILLS_DIR / skill_name / "references" / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""
