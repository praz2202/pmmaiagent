"""
services/orchestration/main.py

FastAPI application — the PMM AI Agent's HTTP layer.
Two main endpoints: start session, respond to PM message.
"""
from __future__ import annotations

import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import structlog
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from session.redis_client import SessionManager
from session.models import PMAgentState
from context_loader.s3_loader import load_company_context, invalidate_cache
from tools.deps import build_deps

logger = structlog.get_logger()
session_manager = SessionManager()


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    import os
    if os.getenv("DYNAMODB_ENDPOINT"):
        # Only auto-create table in local dev (DynamoDB Local)
        from session.session_history import ensure_table_exists
        ensure_table_exists()
    logger.info("startup_complete")
    yield
    # SHUTDOWN
    logger.info("shutdown")


app = FastAPI(title="PMM AI Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten to CloudFront domain in prod
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ── Request/response models ──────────────────────────────────────────────────

class StartRequest(BaseModel):
    pm_name: str   # from frontend dropdown


class EndRequest(BaseModel):
    reason: str = "completed"   # "completed" | "restarted"


class RespondRequest(BaseModel):
    input: str

    @field_validator("input")
    @classmethod
    def sanitize_input(cls, v: str) -> str:
        """Sanitize PM input to prevent prompt injection and abuse."""
        if not v or not v.strip():
            raise ValueError("Input cannot be empty")
        if len(v) > 2000:
            raise ValueError("Input too long (max 2000 characters)")
        # Strip control characters
        v = "".join(c for c in v if c.isprintable() or c in "\n\t")
        # Block known prompt injection patterns
        injection_patterns = [
            r"ignore\s+(all\s+)?previous",
            r"system\s+prompt",
            r"<\|im_start\|>",
            r"<\|im_end\|>",
            r"you\s+are\s+now",
            r"new\s+instructions",
            r"forget\s+(everything|all)",
        ]
        for pattern in injection_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Input contains disallowed content")
        return v.strip()


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.post("/sessions/start")
async def start_session(req: StartRequest):
    from agent import pmm_agent
    from compaction import count_message_chars

    pm_context = load_company_context(req.pm_name)
    session_id = str(uuid.uuid4())
    state = PMAgentState(
        session_id=session_id,
        pm_name=req.pm_name,
        pm_context=pm_context,
        start_time=datetime.now(timezone.utc).isoformat(),
    )

    # Store PM's eGain token (if provided from frontend login)

    deps = build_deps(pm_context, session_id)

    # First agent turn — agent greets the PM
    try:
        result = await pmm_agent.run(
            "PM has started a new session.",
            deps=deps,
            model=deps.llm_model,
            model_settings=deps.model_settings,
        )
        state.message_history = list(result.all_messages())
        state.total_chars = count_message_chars(state.message_history)
    except Exception as e:
        logger.error("agent_error", session_id=session_id, error=str(e))
        return {"session_id": session_id, "message": f"Error: {str(e)}", "awaiting_input": True}

    await session_manager.save(session_id, state)
    return {
        "session_id": session_id,
        "message": result.output,
        "awaiting_input": True,
        "tools_called": _extract_tool_calls(result),
    }


@app.post("/sessions/{session_id}/respond")
async def respond(session_id: str, req: RespondRequest):
    from agent import pmm_agent
    from compaction import maybe_compact, count_message_chars
    from pydantic_ai.agent import AgentRun

    state = await session_manager.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    deps = build_deps(state.pm_context, session_id)
    await maybe_compact(state, deps.llm_model)

    import json as json_mod

    # Map tool names to skill names for display
    TOOL_TO_SKILL = {
        'list_releases': 'Release Features',
        'fetch_release_features': 'Release Features',
        'get_feature_detail': 'Release Features',
        'search_features': 'Feature Search',
        'get_child_topics': 'Portal Articles',
        'browse_portal_topic': 'Portal Articles',
        'read_portal_article': 'Portal Articles',
        'get_release_tracking': 'Context',
        'get_portal_structure': 'Context',
        'get_document_rules': 'Context',
    }

    async def event_stream():
        """SSE stream: sends tool call events during agent execution, then final result."""
        from pydantic_ai.messages import ToolCallPart

        try:
            async with pmm_agent.iter(
                req.input,
                message_history=state.message_history,
                deps=deps,
                model=deps.llm_model,
                model_settings=deps.model_settings,
            ) as agent_run:
                async for node in agent_run:
                    node_name = type(node).__name__

                    if node_name == 'CallToolsNode' and hasattr(node, 'model_response'):
                        # Extract tool calls from the model response
                        for part in node.model_response.parts:
                            if isinstance(part, ToolCallPart):
                                tool = part.tool_name.replace('default_api:', '')
                                skill = TOOL_TO_SKILL.get(tool, '')
                                args = part.args if isinstance(part.args, dict) else {}
                                # Build a readable description
                                arg_str = ', '.join(f'{k}={v}' for k, v in args.items() if v)
                                yield f"data: {json_mod.dumps({'type': 'tool_call', 'tool': tool, 'skill': skill, 'args': arg_str})}\n\n"

                    elif node_name == 'ModelRequestNode':
                        yield f"data: {json_mod.dumps({'type': 'thinking'})}\n\n"

            result = agent_run.result
            state.message_history = list(result.all_messages())
            state.total_chars = count_message_chars(state.message_history)
            await session_manager.save(session_id, state)

            yield f"data: {json_mod.dumps({'type': 'done', 'message': result.output, 'tools_called': _extract_tool_calls(result)})}\n\n"

        except Exception as e:
            logger.warning("agent_iter_error", session_id=session_id, error=str(e))
            # Fallback: retry with agent.run() (no streaming but more robust)
            try:
                yield f"data: {json_mod.dumps({'type': 'thinking'})}\n\n"
                result = await pmm_agent.run(
                    req.input,
                    message_history=state.message_history,
                    deps=deps,
                    model=deps.llm_model,
                    model_settings=deps.model_settings,
                )
                state.message_history = list(result.all_messages())
                state.total_chars = count_message_chars(state.message_history)
                await session_manager.save(session_id, state)
                yield f"data: {json_mod.dumps({'type': 'done', 'message': result.output, 'tools_called': _extract_tool_calls(result)})}\n\n"
            except Exception as e2:
                logger.error("agent_error", session_id=session_id, error=str(e2))
                await session_manager.save(session_id, state)
                yield f"data: {json_mod.dumps({'type': 'error', 'message': str(e2)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _extract_tool_calls(result) -> list[dict]:
    """Extract tool call names and args from the agent result."""
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    calls = []
    for msg in result.all_messages():
        if isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, ToolCallPart):
                    calls.append({
                        "tool": part.tool_name.replace("default_api:", ""),
                        "args": part.args if isinstance(part.args, dict) else {},
                    })
    return calls


@app.get("/sessions/{session_id}/status")
async def status(session_id: str):
    state = await session_manager.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": state.session_id,
        "pm_name": state.pm_name,
        "total_chars": state.total_chars,
        "compaction_count": state.compaction_count,
    }


@app.post("/sessions/{session_id}/end")
async def end_session(session_id: str, req: EndRequest):
    """End session: write history to DynamoDB, clean up Redis."""
    state = await session_manager.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    from session.session_history import save_session_record
    await save_session_record(state, status=req.reason)
    await session_manager.delete(session_id)
    return {"ended": True, "session_id": session_id, "status": req.reason}


@app.get("/pm/resolve")
async def resolve_pm(email: str):
    """Resolve PM email to name using company-context.md."""
    from context_loader.s3_loader import _get_raw_md, _parse_pm_ownership_table
    raw = _get_raw_md()
    pm_rows = _parse_pm_ownership_table(raw)
    for row in pm_rows:
        if row["email"].strip().lower() == email.lower():
            return {"name": row["name"].strip(), "email": row["email"].strip()}
    raise HTTPException(status_code=404, detail=f"PM with email '{email}' not found")


@app.post("/internal/context/invalidate")
async def invalidate_context():
    """Called by Lambda when company-context.md is updated in S3."""
    invalidate_cache()
    return {"invalidated": True}


@app.get("/internal/tools/list")
async def list_tools():
    """List all registered tools — for debugging."""
    from agent import ALL_TOOLS
    return {"tools": [t.__name__ for t in ALL_TOOLS], "count": len(ALL_TOOLS)}
