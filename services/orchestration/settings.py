"""
services/orchestration/settings.py

LLM provider configuration, compaction thresholds, and app settings.
Change DEFAULT_PROVIDER to switch all agent nodes — no code changes needed.
"""
from __future__ import annotations

import os

# ── LLM Provider Configuration ───────────────────────────────────────────────

PROVIDERS = {
    "gemini": {
        "name": "Gemini",
        "model": "gemini-3-flash-preview",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "credentials_secret": "pmm-agent/gemini-api-key",
    },
    "anthropic": {
        "name": "Anthropic",
        "model": "claude-sonnet-4-20250514",
        "base_url": "https://api.anthropic.com/v1/",
        "api_key_env": "CLAUDE_API_KEY",
        "credentials_secret": "pmm-agent/anthropic-api-key",
    },
    "openai": {
        "name": "OpenAI",
        "model": "gpt-4o",
        "base_url": "https://api.openai.com/v1/",
        "api_key_env": "OPENAI_API_KEY",
        "credentials_secret": "pmm-agent/openai-api-key",
    },
}

DEFAULT_PROVIDER = "gemini"

DEFAULT_MODEL_SETTINGS = {
    "extra_body": {"reasoning_effort": "low"},
}

# ── Context Window & Compaction ──────────────────────────────────────────────

# Context window budget: 480,000 chars ≈ 120,000 tokens (4 chars/token avg)
CONTEXT_WINDOW_CHARS = 480_000

# Compaction triggers at 90% of context window (432,000 chars ≈ 108k tokens)
COMPACTION_TRIGGER_RATIO = 0.90
COMPACTION_TRIGGER_CHARS = int(CONTEXT_WINDOW_CHARS * COMPACTION_TRIGGER_RATIO)

# Max tokens for the compaction summary: up to 12,000 tokens (48,000 chars)
COMPACTION_MAX_TOKENS = 12_000
COMPACTION_MAX_CHARS = COMPACTION_MAX_TOKENS * 4  # 48,000 chars ≈ 10% of context

# Only the last turn is kept verbatim — everything else is summarized
PROTECTED_TAIL_TURNS = 1

# Max chars for a single tool response before it's capped
MAX_TOOL_RESPONSE_CHARS = 60_000

# ── App Settings ─────────────────────────────────────────────────────────────

APP_ENV = os.getenv("APP_ENV", "local")
LOG_LEVEL = os.getenv("LOG_LEVEL", "debug")
LOGFIRE_TOKEN = os.getenv("LOGFIRE_TOKEN", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
DYNAMODB_ENDPOINT = os.getenv("DYNAMODB_ENDPOINT", "http://localhost:8042")
CONTEXT_BUCKET = os.getenv("CONTEXT_BUCKET", "egain-pmm-agent-context-066148154898")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-west-2")
FRONTEND_ORIGIN_DEV = os.getenv("FRONTEND_ORIGIN_DEV", "http://localhost:3000")
FRONTEND_ORIGIN_PROD = os.getenv("FRONTEND_ORIGIN_PROD", "https://pmm-agent.egain.com")
