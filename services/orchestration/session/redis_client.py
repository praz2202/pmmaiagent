"""
services/orchestration/session/redis_client.py

Manages live session state in Redis.
Each session is stored as JSON under key: session:{session_id}
TTL: 24 hours — sessions expire automatically if abandoned.
"""
from __future__ import annotations

import os

import redis.asyncio as redis_async

from session.models import PMAgentState


# ── Redis connection (process-level singleton) ───────────────────────────────

_redis_client = None


async def get_redis():
    """Get or create the shared async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_async.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379"),
            decode_responses=True,
        )
    return _redis_client


# ── Session Manager ──────────────────────────────────────────────────────────

class SessionManager:
    """Save, load, and delete PMAgentState in Redis."""

    TTL = 86400  # 24 hours in seconds

    def __init__(self):
        self._redis = None

    async def _get_client(self):
        if not self._redis:
            self._redis = await get_redis()
        return self._redis

    async def get(self, session_id: str) -> PMAgentState | None:
        """Load session state from Redis. Returns None if not found or expired."""
        r = await self._get_client()
        raw = await r.get(f"session:{session_id}")
        return PMAgentState.model_validate_json(raw) if raw else None

    async def save(self, session_id: str, state: PMAgentState) -> None:
        """Save session state to Redis with 24h TTL."""
        r = await self._get_client()
        await r.setex(f"session:{session_id}", self.TTL, state.model_dump_json())

    async def delete(self, session_id: str) -> None:
        """Delete session from Redis (called on session end or restart)."""
        r = await self._get_client()
        await r.delete(f"session:{session_id}")
