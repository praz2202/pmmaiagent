"""
config/skills/release_features/tools.py

Release feature tools — registered on the PMM AI Agent.
Two-level fetch: Level 1 (lightweight list) then Level 2 (full detail on demand).
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
        pm_name = ctx.deps.pm_context.name
        return (
            f"I can only access products you own ({', '.join(owned)}). "
            f"{product_key} is managed by a different PM. "
            f"Please reach out to the PM who owns {product_key} for that information."
        )
    return None


# ── Level 1: Feature list ────────────────────────────────────────────────────

async def list_releases(ctx: RunContext[AgentDeps], product_key: str) -> Any:
    """List releases for a product. Returns release IDs, names, and status.
    Use to find the release_id for standard products (ECAI, ECKN, ECAD).
    NOT needed for AIA — AIA uses version tags, not release IDs.

    Args:
        product_key: Aha product key: 'ECAI', 'ECKN', or 'ECAD'.
    """
    if err := _check_product_access(ctx, product_key):
        return {"error": err}
    return await aha_api_call("GET", f"/products/{product_key}/releases", {"per_page": "200"})


async def fetch_release_features(
    ctx: RunContext[AgentDeps],
    product_key: str,
    release_id: str | None = None,
    tag: str | None = None,
) -> Any:
    """Get feature LIST for a release — titles, Jira URLs, Documents Impacted tags.
    This is the lightweight Level 1 fetch. Does NOT return full descriptions.

    For standard products (ECAI, ECKN, ECAD): pass product_key + release_id.
    For AIA: pass product_key + tag (e.g. tag='AIA 1.2.0').

    Args:
        product_key: Aha product key: 'AIA', 'ECAI', 'ECKN', or 'ECAD'.
        release_id: Release ID from list_releases. Required for ECAI/ECKN/ECAD.
        tag: AIA version tag, e.g. 'AIA 1.2.0'. Required for AIA.
    """
    if err := _check_product_access(ctx, product_key):
        return {"error": err}
    if tag:
        path = f"/products/{product_key}/features"
        tag_clean = tag.strip()
        params = {"tag": tag_clean, "fields": "name,custom_fields,tags,integration_fields"}
        result = await aha_api_call("GET", path, params)
        # Some Aha tags have trailing spaces — retry with space if no results
        if not (result.get("features") if isinstance(result, dict) else None):
            params["tag"] = tag_clean + " "
            result = await aha_api_call("GET", path, params)
        return result
    else:
        path = f"/releases/{release_id}/features"
        params = {"fields": "name,custom_fields,tags,integration_fields"}
        return await aha_api_call("GET", path, params)


# ── Level 2: Full detail ─────────────────────────────────────────────────────

async def get_feature_detail(ctx: RunContext[AgentDeps], feature_id: str) -> Any:
    """Get FULL content for a single feature — description, attachments,
    all custom fields, and requirements (sub-tasks).
    Only call after PM confirms which features to work with.

    Args:
        feature_id: Feature ID, e.g. 'AIA-42' or 'ECAI-123'.
    """
    # Extract product key from feature ID (e.g. "ECAI-123" → "ECAI")
    product_key = feature_id.split("-")[0] if "-" in feature_id else ""
    if product_key and (err := _check_product_access(ctx, product_key)):
        return {"error": err}
    return await aha_api_call("GET", f"/features/{feature_id}", {
        "fields": "name,description,custom_fields,tags,attachments,integration_fields,requirements",
    })


RELEASE_FEATURES_TOOLS = [
    list_releases,
    fetch_release_features,
    get_feature_detail,
]
