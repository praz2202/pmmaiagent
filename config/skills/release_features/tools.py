"""
config/skills/release-features/tools.py

Release feature tools — registered on the PMM AI Agent.
Two-level fetch: Level 1 (lightweight list) then Level 2 (full detail on demand).
Calls Aha API via the shared pmm-skill-client Lambda.
"""
from __future__ import annotations

from typing import Any
from pydantic_ai import RunContext
from tools.deps import AgentDeps

AHA_API_CONFIG = {
    "name": "aha",
    "base_url": "https://{subdomain}.aha.io/api/v1",
    "auth": {
        "type": "basic",
        "credentials_secret": "pmm-agent/aha-api-key",
        "secret_field": "api_key",
    },
}


# ── Level 1: Feature list ────────────────────────────────────────────────────

async def list_releases(ctx: RunContext[AgentDeps], product_key: str) -> Any:
    """List releases for a product. Returns release IDs, names, and status.
    Use to find the release_id for standard products (ECAI, ECKN, ECAD).
    NOT needed for AIA — AIA uses version tags, not release IDs.

    Args:
        product_key: Aha product key: 'ECAI', 'ECKN', or 'ECAD'.
    """
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": f"/products/{product_key}/releases",
        "params": {},
        "api_config": AHA_API_CONFIG,
    })


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
        params = {"tag": tag, "fields": "name,custom_fields,tags"}
    else:
        path = f"/releases/{release_id}/features"
        params = {"fields": "name,custom_fields,tags"}
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": path,
        "params": params,
        "api_config": AHA_API_CONFIG,
    })


# ── Level 2: Full detail ─────────────────────────────────────────────────────

async def get_feature_detail(ctx: RunContext[AgentDeps], feature_id: str) -> Any:
    """Get FULL content for a single feature — description, attachments,
    all custom fields. Only call after PM confirms which features to work with.

    Args:
        feature_id: Feature ID, e.g. 'AIA-42' or 'ECAI-123'.
    """
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": f"/features/{feature_id}",
        "params": {"fields": "name,description,custom_fields,tags,attachments"},
        "api_config": AHA_API_CONFIG,
    })


RELEASE_FEATURES_TOOLS = [
    list_releases,
    fetch_release_features,
    get_feature_detail,
]
