"""
config/skills/portal_articles/tools.py

Portal article tools — registered on the PMM AI Agent.
Read-only. Calls eGain Knowledge API v4 via the shared pmm-skill-client Lambda.

ID format: eGain v4 APIs accept SHORT IDs only.
Long ID (from company-context.md): 308200000003062
Short ID (for API calls):          EASY-3062 (last 4 digits)
"""
from __future__ import annotations

from typing import Any
from pydantic_ai import RunContext
from tools.deps import AgentDeps

EGAIN_API_CONFIG = {
    "name": "egain",
    "base_url": "https://api.egain.cloud/apis/v4/knowledge/portalmgr/api-bundled",
    "auth": {
        "type": "basic_onbehalf",
        "credentials_secret": "pmm-agent/egain-credentials",
        "client_id_field": "client_id",
        "client_secret_field": "client_secret",
    },
}


def _to_short_id(long_id: str) -> str:
    """Convert long topic/portal ID to short form for eGain v4 API.
    '308200000003062' → 'EASY-3062' (EASY- + last 4 digits).
    If already short (starts with EASY-), return as-is.
    """
    if long_id.startswith("EASY-"):
        return long_id
    return f"EASY-{long_id[-4:]}"


# ── Topic navigation ─────────────────────────────────────────────────────────

async def get_child_topics(
    ctx: RunContext[AgentDeps],
    parent_topic_id: str,
) -> Any:
    """Get child sub-topics under a parent topic. Use to discover sub-topics
    like 'Connectors', 'Channels', 'New Features for AI Agent 1.2.0', etc.

    company-context.md only has TOP-LEVEL topic IDs. Call this to discover
    what's underneath. Max depth is 2 levels (topic → sub-topic → sub-sub-topic).

    Args:
        parent_topic_id: Topic ID from company-context.md (e.g. '308200000003062').
                         Accepts both long and short format.
    """
    short_id = _to_short_id(parent_topic_id)
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": "/topic/getchildtopics",
        "params": {"topicId": short_id},
        "api_config": EGAIN_API_CONFIG,
    })


# ── Articles ─────────────────────────────────────────────────────────────────

async def browse_portal_topic(
    ctx: RunContext[AgentDeps],
    topic_id: str,
) -> Any:
    """List articles in a topic. Returns article titles and article_summary.
    Use to survey existing content before deciding update vs create.
    Works at any level — top-level topics, sub-topics, or sub-sub-topics.

    Args:
        topic_id: Topic ID (e.g. '308200000003062'). Accepts both long and short format.
    """
    short_id = _to_short_id(topic_id)
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": "/article/getarticlesintopic",
        "params": {"topicId": short_id},
        "api_config": EGAIN_API_CONFIG,
    })


async def read_portal_article(
    ctx: RunContext[AgentDeps],
    article_id: str,
) -> Any:
    """Get full article content including HTML body. Only call when title/summary
    suggests this article needs updating or when you need to read content to decide.

    Args:
        article_id: Article short ID (e.g. 'EASY-17468').
    """
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": "/article/getarticlebyid",
        "params": {"articleId": article_id},
        "api_config": EGAIN_API_CONFIG,
    })


PORTAL_ARTICLES_TOOLS = [
    get_child_topics,
    browse_portal_topic,
    read_portal_article,
]
