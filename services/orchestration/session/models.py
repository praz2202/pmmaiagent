"""
services/orchestration/session/models.py

All Pydantic models for session state and domain objects.
PMAgentState is the session state — serialised to Redis between PM messages.
Contains no credentials.
"""
from __future__ import annotations


from pydantic import BaseModel


# ── Company context models (parsed from company-context.md) ──────────────────

class AhaMapping(BaseModel):
    """Per-product Aha configuration."""
    product: str                        # "AI Agent", "AI Services", etc.
    aha_product_key: str                # "AIA", "ECAI", "ECKN", "ECAD"
    release_field_type: str             # "aia_version_tag" | "standard_release"
    aia_version_prefix: str | None = None  # "AIA" for AIA product, None otherwise


class PortalTopic(BaseModel):
    """A topic in the eGain portal hierarchy."""
    name: str
    topic_id: str
    product: str | None = None          # which product this topic belongs to
    notes: str | None = None


class PortalContext(BaseModel):
    """Shared portal configuration — one portal for all products."""
    portal_short_id: str                # "2ibo79"
    topics: list[PortalTopic] = []      # flat list of all topics with IDs


class PMContext(BaseModel):
    """Parsed from company-context.md at session start. Read-only during session."""
    pm_id: str                          # derived from email (before @)
    name: str
    email: str
    egain_username: str | None = None   # eGain login username (for On-Behalf-Of auth)
    owned_products: list[str]           # ["AIA", "ECAI"]
    reports_to: str | None = None
    aha_mappings: dict[str, AhaMapping]  # product_code → AhaMapping
    portal_context: PortalContext
    release_cadence_rules: str = ""
    documents_impacted_rules: str = ""  # Documents Impacted tag meanings (injected into prompts)


# ── Audit models ─────────────────────────────────────────────────────────────

class ToolCallRecord(BaseModel):
    """Recorded per tool call — full response is never stored."""
    tool_name: str
    params: dict
    timestamp: str                      # ISO 8601
    result: str = "tool response received"


# ── Session state (Redis) ─────────────────────────────────────────────────────

class PMAgentState(BaseModel):
    """
    Session state — serialised to Redis between PM messages.
    Contains NO credentials. The agent tracks everything else
    in its conversation history (message_history).
    """
    session_id: str
    pm_name: str                        # from frontend dropdown
    pm_context: PMContext | None = None

    # ── Conversation ──────────────────────────────────────────────────────
    message_history: list = []          # pydantic-ai ModelMessage list
    total_chars: int = 0                # for compaction trigger
    compaction_count: int = 0
    compacted_summary: str | None = None

    # ── Audit ─────────────────────────────────────────────────────────────
    tool_calls: list[ToolCallRecord] = []
    start_time: str | None = None       # ISO 8601


# ── Session history (DynamoDB) ───────────────────────────────────────────────

class ChatMessage(BaseModel):
    """A single user/assistant message for conversation replay."""
    role: str                           # "user" | "assistant"
    content: str


class SessionRecord(BaseModel):
    """Written to DynamoDB once at session end. Never updated."""
    session_id: str                     # partition key
    pm_name: str
    pm_email: str
    start_time: str
    end_time: str
    status: str                         # "completed" | "restarted"
    title: str = ""                     # first user message — for history sidebar
    messages: list[ChatMessage] = []    # conversation for replay
    tool_calls: list[ToolCallRecord] = []
