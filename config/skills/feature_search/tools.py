"""
config/skills/feature-search/tools.py

Feature search tool — registered on the PMM AI Agent.
Calls Aha API via the shared pmm-skill-client Lambda.
"""
from __future__ import annotations

from typing import Any
from pydantic_ai import RunContext
from tools.deps import AgentDeps

# Reuse the same Aha API config
from config.skills.release_features.tools import AHA_API_CONFIG


async def search_features(
    ctx: RunContext[AgentDeps],
    product_key: str,
    query: str,
) -> Any:
    """Search features by keyword/title within an Aha product. Use when a PM
    remembers a vague feature name. Returns matching features with title,
    ID, and Aha link.

    Args:
        product_key: Aha product key: 'AIA', 'ECAI', 'ECKN', or 'ECAD'.
        query: Search keyword — the feature name or part of it.
    """
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": f"/products/{product_key}/features",
        "params": {"q": query, "fields": "name,custom_fields,tags"},
        "api_config": AHA_API_CONFIG,
    })


FEATURE_SEARCH_TOOLS = [
    search_features,
]
