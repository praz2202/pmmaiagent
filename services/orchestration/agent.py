"""
services/orchestration/agent.py

The PMM AI Agent — one PydanticAI Agent with all tools registered.
Multi-turn conversation with PMs via message_history.
"""
from __future__ import annotations

from pydantic_ai import Agent, RunContext

from tools.deps import AgentDeps
from context_loader.prompt_loader import load_prompt
from context_loader.skill_loader import load_skill_md

# ── Import all tool functions ────────────────────────────────────────────────

from config.skills.release_features.tools import RELEASE_FEATURES_TOOLS
from config.skills.feature_search.tools import FEATURE_SEARCH_TOOLS
from config.skills.portal_articles.tools import PORTAL_ARTICLES_TOOLS
from config.skills.context.tools import CONTEXT_TOOLS


# ── Skill loading tool ───────────────────────────────────────────────────────

async def load_skill(ctx: RunContext[AgentDeps], skill_name: str) -> str:
    """Load full instructions for a skill. Call this BEFORE starting a task
    that requires the skill. Available skills: release_features, feature_search,
    release_notes, portal_articles.

    Args:
        skill_name: One of: 'release_features', 'feature_search', 'release_notes', 'portal_articles'.
    """
    valid_skills = ['release_features', 'feature_search', 'release_notes', 'portal_articles']
    if skill_name not in valid_skills:
        return f"Unknown skill '{skill_name}'. Available: {', '.join(valid_skills)}"

    content = load_skill_md(skill_name)
    if not content:
        return f"Skill '{skill_name}' has no instructions file."
    return content


ALL_TOOLS = (
    RELEASE_FEATURES_TOOLS
    + FEATURE_SEARCH_TOOLS
    + PORTAL_ARTICLES_TOOLS
    + CONTEXT_TOOLS
    + [load_skill]
)

# ── Create the agent ─────────────────────────────────────────────────────────

pmm_agent: Agent[AgentDeps, str] = Agent(
    deps_type=AgentDeps,
    output_type=str,
    tools=ALL_TOOLS,
)


# ── System prompt (dynamic — injected per session) ───────────────────────────

@pmm_agent.instructions
async def system_instructions(ctx) -> str:
    """Build the system prompt from template + PM context."""
    pm = ctx.deps.pm_context
    template = load_prompt("system")

    prompt = template.replace("{pm_name}", pm.name)
    prompt = prompt.replace("{pm_products}", ", ".join(pm.owned_products))
    prompt = prompt.replace("{pm_reports_to}", pm.reports_to or "—")

    return prompt
