"""
services/orchestration/agent.py

The PMM AI Agent — one PydanticAI Agent with all tools registered.
Multi-turn conversation with PMs via message_history.
"""
from __future__ import annotations

from pydantic_ai import Agent

from tools.deps import AgentDeps
from context_loader.prompt_loader import load_prompt
from context_loader.skill_loader import load_skill_md

# ── Import all tool functions ────────────────────────────────────────────────

from config.skills.release_features.tools import RELEASE_FEATURES_TOOLS
from config.skills.feature_search.tools import FEATURE_SEARCH_TOOLS
from config.skills.portal_articles.tools import PORTAL_ARTICLES_TOOLS
from config.skills.context.tools import CONTEXT_TOOLS

ALL_TOOLS = (
    RELEASE_FEATURES_TOOLS
    + FEATURE_SEARCH_TOOLS
    + PORTAL_ARTICLES_TOOLS
    + CONTEXT_TOOLS
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
    """Build the system prompt from template + PM context + skill instructions."""
    pm = ctx.deps.pm_context
    template = load_prompt("system")

    # Load skill SKILL.md content for injection
    release_features_skill = load_skill_md("release_features")
    release_notes_skill = load_skill_md("release_notes")
    portal_articles_skill = load_skill_md("portal_articles")
    feature_search_skill = load_skill_md("feature_search")

    # Use replace instead of .format() — .format() breaks on literal {version} etc in the template
    prompt = template.replace("{pm_name}", pm.name)
    prompt = prompt.replace("{pm_products}", ", ".join(pm.owned_products))
    prompt = prompt.replace("{pm_reports_to}", pm.reports_to or "—")

    return prompt + (
        "\n\n--- Skill: Release Features ---\n" + release_features_skill
        + "\n\n--- Skill: Release Notes ---\n" + release_notes_skill
        + "\n\n--- Skill: Portal Articles ---\n" + portal_articles_skill
        + "\n\n--- Skill: Feature Search ---\n" + feature_search_skill
    )
