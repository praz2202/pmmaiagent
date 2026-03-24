"""
config/skills/portal_articles/tools.py

Portal article tools — registered on the PMM AI Agent.
Read-only. Calls eGain Knowledge API v4.

API: https://api.egain.cloud/knowledge/portalmgr/v4/portals/{portalId}/...
Auth: OAuth 2.0 Client Credentials (token cached process-level)
"""
from __future__ import annotations

from typing import Any
from pydantic_ai import RunContext
from tools.deps import AgentDeps
from tools.api_client import egain_api_call


def _to_short_id(long_id: str) -> str:
    """Convert long topic/portal ID to short form.
    '308200000003062' → 'EASY-3062' (EASY- + last 4 digits).
    If already short (starts with EASY-), return as-is.
    """
    if long_id.startswith("EASY-"):
        return long_id
    return f"EASY-{long_id[-4:]}"


# ── Topic navigation ─────────────────────────────────────────────────────────

async def get_child_topics(
    ctx: RunContext[AgentDeps],
    topic_id: str,
) -> Any:
    """Get a topic and its child sub-topics. Returns the topic tree with names,
    article counts, and sub-topic IDs. Use to discover sub-topics like
    'Connectors', 'New Features for AI Agent 1.2.0', etc.

    company-context.md only has TOP-LEVEL topic IDs. Call this to discover
    what's underneath. Max depth is 2 levels.

    Args:
        topic_id: Topic ID (e.g. '308200000003062' or 'EASY-3062').
    """
    short_id = _to_short_id(topic_id)
    portal_id = ctx.deps.pm_context.portal_context.portal_short_id
    return await egain_api_call(
        "GET",
        f"/portals/{portal_id}/topics/{short_id}",
        params={"level": "1", "$lang": "en-US"},
    )


# ── Articles ─────────────────────────────────────────────────────────────────

async def browse_portal_topic(
    ctx: RunContext[AgentDeps],
    topic_id: str,
) -> Any:
    """List articles in a topic. Returns article names, IDs, created/modified info.
    Use to survey existing content before deciding update vs create.
    Works at any level — top-level topics, sub-topics, or sub-sub-topics.

    Args:
        topic_id: Topic ID (e.g. '308200000003062' or 'EASY-3062').
    """
    short_id = _to_short_id(topic_id)
    portal_id = ctx.deps.pm_context.portal_context.portal_short_id
    return await egain_api_call(
        "GET",
        f"/portals/{portal_id}/articles",
        params={"$filter[topicId]": short_id},
    )


async def read_portal_article(
    ctx: RunContext[AgentDeps],
    article_id: str,
) -> Any:
    """Get full article content including HTML body. Only call when you need
    to read the article to decide on update or to know exactly what to change.

    NOTE: May require user-scoped token for full content access.

    Args:
        article_id: Article short ID (e.g. 'EASY-17368').
    """
    portal_id = ctx.deps.pm_context.portal_context.portal_short_id
    return await egain_api_call(
        "GET",
        f"/portals/{portal_id}/articles/{article_id}",
    )


PORTAL_ARTICLES_TOOLS = [
    get_child_topics,
    browse_portal_topic,
    read_portal_article,
]
