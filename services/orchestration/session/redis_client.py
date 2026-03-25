"""
services/orchestration/session/redis_client.py

Manages live session state in Redis.
Each session is stored as TWO keys:
  session:{session_id}       — PMAgentState JSON (without message_history)
  session:{session_id}:msgs  — message_history serialized via PydanticAI's ModelMessagesTypeAdapter
TTL: 24 hours — sessions expire automatically if abandoned.
"""
from __future__ import annotations

import os

import redis.asyncio as redis_async
from pydantic_ai.messages import ModelMessagesTypeAdapter

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
    """Save, load, and delete PMAgentState in Redis.

    Message history is stored separately using PydanticAI's
    ModelMessagesTypeAdapter to ensure proper serialization/deserialization
    of ModelRequest/ModelResponse objects.
    """

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

        # Load state (without message_history)
        raw = await r.get(f"session:{session_id}")
        if not raw:
            return None
        state = PMAgentState.model_validate_json(raw)

        # Load message history separately (proper deserialization)
        msgs_raw = await r.get(f"session:{session_id}:msgs")
        if msgs_raw:
            state.message_history = list(
                ModelMessagesTypeAdapter.validate_json(msgs_raw)
            )

        return state

    async def save(self, session_id: str, state: PMAgentState) -> None:
        """Save session state to Redis with 24h TTL."""
        r = await self._get_client()

        # Serialize message history separately
        msgs = state.message_history
        msgs_json = ModelMessagesTypeAdapter.dump_json(msgs).decode() if msgs else "[]"

        # Save state without message_history (it's stored separately)
        state_copy = state.model_copy()
        state_copy.message_history = []  # don't double-store
        await r.setex(f"session:{session_id}", self.TTL, state_copy.model_dump_json())

        # Save message history
        await r.setex(f"session:{session_id}:msgs", self.TTL, msgs_json)

    async def delete(self, session_id: str) -> None:
        """Delete session from Redis (called on session end or restart)."""
        r = await self._get_client()
        await r.delete(f"session:{session_id}", f"session:{session_id}:msgs")
