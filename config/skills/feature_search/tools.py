"""
config/skills/feature_search/tools.py

Feature search tool — registered on the PMM AI Agent.
"""
from __future__ import annotations

from typing import Any
from pydantic_ai import RunContext
from tools.deps import AgentDeps
from tools.api_client import aha_api_call


def _check_product_access(ctx: RunContext[AgentDeps], product_key: str) -> str | None:
    """Check if PM owns this product. Returns error message or None if allowed."""
    owned = ctx.deps.pm_context.owned_products
    if product_key.upper() not in [p.upper() for p in owned]:
        return (
            f"I can only access products you own ({', '.join(owned)}). "
            f"{product_key} is managed by a different PM. "
            f"Please reach out to the PM who owns {product_key} for that information."
        )
    return None


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
    if err := _check_product_access(ctx, product_key):
        return {"error": err}
    return await aha_api_call("GET", f"/products/{product_key}/features", {
        "q": query,
        "fields": "name,custom_fields,tags",
    })


FEATURE_SEARCH_TOOLS = [
    search_features,
]
