"""
config/skills/context/tools.py

Dynamic context loading tools — registered on the PMM AI Agent.
These load context from company-context.md ON DEMAND instead of
dumping everything into the system prompt.
"""
from __future__ import annotations

from typing import Any
from pydantic_ai import RunContext
from tools.deps import AgentDeps


async def get_release_tracking(ctx: RunContext[AgentDeps], product_key: str) -> str:
    """Get release tracking rules for a product. Returns how releases are tracked
    in Aha (version tags for AIA, release attribute for standard products).
    Call this BEFORE fetching features to know the right approach.

    Args:
        product_key: Product code: 'AIA', 'ECAI', 'ECKN', or 'ECAD'.
    """
    pm = ctx.deps.pm_context
    if product_key not in pm.aha_mappings:
        return f"Product '{product_key}' not found in PM's owned products: {pm.owned_products}"

    mapping = pm.aha_mappings[product_key]
    if mapping.release_field_type == "aia_version_tag":
        return (
            f"{product_key} ({mapping.product}): Uses version TAGS, not Release field.\n"
            f"Tags look like: AIA 1.2.0, AIA 2.0.0\n"
            f"Fetch with: fetch_release_features(product_key='{product_key}', tag='AIA x.x.x')\n"
            f"Do NOT use list_releases() for AIA."
        )
    else:
        return (
            f"{product_key} ({mapping.product}): Uses Release ATTRIBUTE.\n"
            f"Release format: {product_key}-R-{{num}} {{version}} (e.g. ECAI-R-53 21.23.1.0)\n"
            f"The actual version is AFTER the space. Ignore the prefix.\n"
            f"Fetch with: list_releases('{product_key}') then fetch_release_features(release_id=...)"
        )


async def get_portal_structure(ctx: RunContext[AgentDeps]) -> str:
    """Get the full eGain portal topic hierarchy with IDs. Returns the topic tree
    so you know which topic_id to pass to browse_portal_topic().
    Call this BEFORE browsing the portal.
    """
    pm = ctx.deps.pm_context
    portal = pm.portal_context

    lines = [
        f"Portal Short ID: {portal.portal_short_id}",
        f"Article ID pattern: EASY-{{number}}",
        "",
        "Topics:",
    ]
    for topic in portal.topics:
        lines.append(f"  - {topic.name} (ID: {topic.topic_id}) [{topic.product}]"
                      + (f" — {topic.notes}" if topic.notes else ""))

    return "\n".join(lines)


async def get_document_rules(ctx: RunContext[AgentDeps]) -> str:
    """Get the Documents Impacted attribute rules — what each tag means and
    how to handle contradictions. Call this when processing feature tags.
    """
    pm = ctx.deps.pm_context
    return pm.documents_impacted_rules or (
        "Documents Impacted tag rules not found in company context. "
        "Ask PM for guidance on which features need documentation."
    )


CONTEXT_TOOLS = [
    get_release_tracking,
    get_portal_structure,
    get_document_rules,
]
