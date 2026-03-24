"""
config/skills/feature_search/tools.py

Feature search tool — registered on the PMM AI Agent.
"""
from __future__ import annotations

from typing import Any
from pydantic_ai import RunContext
from tools.deps import AgentDeps
from tools.api_client import aha_api_call


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
    return await aha_api_call("GET", f"/products/{product_key}/features", {
        "q": query,
        "fields": "name,custom_fields,tags",
    })


FEATURE_SEARCH_TOOLS = [
    search_features,
]
