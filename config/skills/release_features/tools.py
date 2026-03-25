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


# ── Level 1: Feature list ────────────────────────────────────────────────────

async def list_releases(ctx: RunContext[AgentDeps], product_key: str) -> Any:
    """List releases for a product. Returns release IDs, names, and status.
    Use to find the release_id for standard products (ECAI, ECKN, ECAD).
    NOT needed for AIA — AIA uses version tags, not release IDs.

    Args:
        product_key: Aha product key: 'ECAI', 'ECKN', or 'ECAD'.
    """
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
    if tag:
        path = f"/products/{product_key}/features"
        params = {"tag": tag, "fields": "name,custom_fields,tags,integration_fields"}
    else:
        path = f"/releases/{release_id}/features"
        params = {"fields": "name,custom_fields,tags,integration_fields"}
    return await aha_api_call("GET", path, params)


# ── Level 2: Full detail ─────────────────────────────────────────────────────

async def get_feature_detail(ctx: RunContext[AgentDeps], feature_id: str) -> Any:
    """Get FULL content for a single feature — description, attachments,
    all custom fields. Only call after PM confirms which features to work with.

    Args:
        feature_id: Feature ID, e.g. 'AIA-42' or 'ECAI-123'.
    """
    return await aha_api_call("GET", f"/features/{feature_id}", {
        "fields": "name,description,custom_fields,tags,attachments,integration_fields",
    })


RELEASE_FEATURES_TOOLS = [
    list_releases,
    fetch_release_features,
    get_feature_detail,
]
