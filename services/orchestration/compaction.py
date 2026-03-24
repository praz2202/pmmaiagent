"""
services/orchestration/compaction.py

Context window management — compacts message history when it approaches the limit.

Compaction runs BETWEEN conversation turns (not mid-turn). After the PM sends
a message, FastAPI calls maybe_compact() BEFORE the next graph step begins.

After compaction, message_history is permanently replaced with:
  [summary_message] + [last_turn_messages]
The summary occupies up to ~10% of context. Everything else is gone.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    UserPromptPart,
)

from settings import (
    COMPACTION_TRIGGER_CHARS,
    COMPACTION_MAX_TOKENS,
    CONTEXT_WINDOW_CHARS,
    MAX_TOOL_RESPONSE_CHARS,
    PROTECTED_TAIL_TURNS,
)
from context_loader.prompt_loader import load_prompt

logger = structlog.get_logger()


# ── Tool response cap (used inside tool functions) ───────────────────────────

def cap_tool_response(tool_name: str, response: str) -> str:
    """Enforce MAX_TOOL_RESPONSE_CHARS limit and prepend a fetch timestamp.

    Called inside each tool function before returning the result.
    The timestamp helps the agent judge data freshness and
    survives compaction (it's part of the protected last turn).
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    if len(response) <= MAX_TOOL_RESPONSE_CHARS:
        return f"[Retrieved at {timestamp}]\n{response}"

    return (
        f"[Tool '{tool_name}' called at {timestamp} but response was truncated: "
        f"response size ({len(response)} chars) exceeds "
        f"{MAX_TOOL_RESPONSE_CHARS} character limit.]"
    )


# ── Main compaction function ─────────────────────────────────────────────────

async def maybe_compact(state, model) -> bool:
    """Check if compaction is needed and perform it if so.

    Called between turns — after PM sends a message, before the next
    graph step begins.

    After compaction, message_history is permanently replaced with:
      [summary_message] + [last_turn_messages]
    The summary is up to 12k tokens (48k chars) — as concise as possible.
    The last turn stays verbatim. Everything else is gone permanently.

    Returns True if compaction was performed, False otherwise.
    """
    messages = state.message_history
    total_chars = state.total_chars

    logger.info(
        "compaction_check",
        total_chars=total_chars,
        trigger_threshold=COMPACTION_TRIGGER_CHARS,
        message_count=len(messages),
        needed=total_chars > COMPACTION_TRIGGER_CHARS,
    )

    if total_chars <= COMPACTION_TRIGGER_CHARS:
        return False

    # 1. Split: everything before last turn | last turn
    last_turn_idx = _find_protected_tail_start(messages)
    compactable = messages[:last_turn_idx]
    last_turn = messages[last_turn_idx:]

    if not compactable:
        logger.info("compaction_skipped", reason="only last turn in history")
        return False

    # 2. Serialize compactable messages for summarization
    conversation_text = _serialize_messages(compactable)

    logger.info(
        "compacting",
        compactable_messages=len(compactable),
        last_turn_messages=len(last_turn),
        compactable_chars=count_message_chars(compactable),
    )

    # 3. LLM summarization — up to 12k tokens, as concise as possible
    compaction_prompt = load_prompt("COMPACTION_PROMPT")
    summary = await _llm_summarize(
        model,
        user_prompt=compaction_prompt.format(conversation=conversation_text),
        max_tokens=COMPACTION_MAX_TOKENS,
    )

    # 4. Permanently replace message history: [summary] + [last turn]
    summary_msg = ModelRequest(parts=[UserPromptPart(
        content=f"[COMPACTED CONVERSATION SUMMARY — compaction #{state.compaction_count + 1}]\n{summary}"
    )])
    chars_before = total_chars
    state.message_history = [summary_msg] + list(last_turn)
    state.compaction_count += 1
    state.compacted_summary = summary
    state.total_chars = count_message_chars(state.message_history)

    logger.info(
        "compaction_complete",
        compaction_count=state.compaction_count,
        chars_before=chars_before,
        chars_after=state.total_chars,
        reduction_pct=round((1 - state.total_chars / chars_before) * 100, 1),
        summary_chars=len(summary),
        context_pct_used=round(state.total_chars / CONTEXT_WINDOW_CHARS * 100, 1),
    )

    return True


# ── Helpers ──────────────────────────────────────────────────────────────────

def count_message_chars(messages: list[ModelMessage]) -> int:
    """Count total characters across all message parts.
    Called after each agent run to update state.total_chars.
    """
    total = 0
    for msg in messages:
        for part in msg.parts:
            if hasattr(part, "content"):
                content = part.content
                if isinstance(content, str):
                    total += len(content)
            if hasattr(part, "args"):
                total += len(str(part.args))
    return total


def _find_protected_tail_start(messages: list[ModelMessage]) -> int:
    """Find the index where the protected last turn begins.
    Walks backward, counting user turns. Protects only the last 1 turn.
    """
    if not messages:
        return 0

    turns_found = 0
    i = len(messages) - 1

    while i >= 0:
        msg = messages[i]
        if isinstance(msg, ModelRequest):
            has_user_prompt = any(
                isinstance(part, UserPromptPart) for part in msg.parts
            )
            if has_user_prompt:
                turns_found += 1
                if turns_found >= PROTECTED_TAIL_TURNS:
                    return i
        i -= 1

    return 0


def _serialize_messages(messages: list[ModelMessage]) -> str:
    """Convert messages to readable text for the compaction prompt."""
    lines: list[str] = []
    for msg in messages:
        ts = _extract_timestamp(msg)
        ts_prefix = f"[{ts.strftime('%H:%M:%S')}] " if ts else ""

        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                content = getattr(part, "content", "")
                if isinstance(content, str) and content:
                    lines.append(f"{ts_prefix}[{type(part).__name__}] {content}")
        elif isinstance(msg, ModelResponse):
            for part in msg.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    lines.append(f"{ts_prefix}[{type(part).__name__}] {part.content}")
                elif hasattr(part, "args"):
                    tool_name = getattr(part, "tool_name", "unknown")
                    lines.append(f"{ts_prefix}[{type(part).__name__}] tool={tool_name} args={part.args}")

    return "\n".join(lines)


def _extract_timestamp(msg: ModelMessage):
    """Extract native timestamp from a pydantic-ai ModelMessage."""
    if isinstance(msg, ModelResponse):
        return msg.timestamp
    if isinstance(msg, ModelRequest):
        if msg.timestamp is not None:
            return msg.timestamp
        for part in msg.parts:
            if isinstance(part, UserPromptPart):
                return part.timestamp
    return None


# ── LLM summarization ───────────────────────────────────────────────────────

_compaction_agent = Agent(model=None, output_type=str)


async def _llm_summarize(model, user_prompt: str, max_tokens: int) -> str:
    """Call the LLM to produce a compaction summary.
    Uses the same model as the rest of the app (Gemini Flash by default).
    """
    result = await _compaction_agent.run(
        user_prompt=user_prompt,
        model=model,
        model_settings={"max_tokens": max_tokens, "temperature": 0.2},
    )
    return result.output
