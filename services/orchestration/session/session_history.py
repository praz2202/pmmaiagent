"""
services/orchestration/session/session_history.py

Writes SessionRecord to DynamoDB at session end. Write-once, never updated.
Tool call results are stored as "tool response received" — never full responses.

Local dev: uses DynamoDB Local (http://localhost:8042)
Production: uses real AWS DynamoDB
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import boto3

from session.models import ChatMessage, PMAgentState, SessionRecord

TABLE_NAME = "pmm-agent-sessions"


def _get_dynamodb_resource():
    """Get DynamoDB resource — local or prod based on DYNAMODB_ENDPOINT."""
    endpoint = os.getenv("DYNAMODB_ENDPOINT")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")

    if endpoint:
        return boto3.resource(
            "dynamodb",
            region_name=region,
            endpoint_url=endpoint,
            aws_access_key_id="local",
            aws_secret_access_key="local",
        )
    else:
        return boto3.resource("dynamodb", region_name=region)


def ensure_table_exists() -> None:
    """Create the DynamoDB table if it doesn't exist (for local dev)."""
    ddb = _get_dynamodb_resource()
    existing = [t.name for t in ddb.tables.all()]
    if TABLE_NAME in existing:
        return

    ddb.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "session_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "session_id", "AttributeType": "S"},
            {"AttributeName": "pm_email", "AttributeType": "S"},
            {"AttributeName": "start_time", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "pm_email-start_time-index",
                "KeySchema": [
                    {"AttributeName": "pm_email", "KeyType": "HASH"},
                    {"AttributeName": "start_time", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    ddb.Table(TABLE_NAME).wait_until_exists()


def _extract_title(state: PMAgentState) -> str:
    """Extract a title from the first user message in the conversation."""
    from pydantic_ai.messages import ModelRequest, UserPromptPart

    for msg in state.message_history:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    text = part.content.strip()
                    if text == "PM has started a new session.":
                        continue
                    return text[:100] if len(text) > 100 else text
    return "New conversation"


def _extract_messages(state: PMAgentState) -> list[ChatMessage]:
    """Extract user/assistant messages for conversation replay."""
    from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart

    messages = []
    for msg in state.message_history:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, UserPromptPart) and isinstance(part.content, str):
                    text = part.content.strip()
                    if text == "PM has started a new session.":
                        continue
                    if text.startswith("[COMPACTED CONVERSATION SUMMARY"):
                        continue
                    messages.append(ChatMessage(role="user", content=text))
        elif isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, TextPart) and part.content:
                    messages.append(ChatMessage(role="assistant", content=part.content))
    return messages


async def save_session_record(state: PMAgentState, status: str) -> None:
    """Build SessionRecord from live state and write to DynamoDB."""
    record = SessionRecord(
        session_id=state.session_id,
        pm_name=state.pm_name,
        pm_email=state.pm_context.email if state.pm_context else "",
        start_time=state.start_time or "",
        end_time=datetime.now(timezone.utc).isoformat(),
        status=status,
        title=_extract_title(state),
        messages=_extract_messages(state),
        tool_calls=state.tool_calls,
    )

    ddb = _get_dynamodb_resource()
    table = ddb.Table(TABLE_NAME)
    table.put_item(Item=record.model_dump())


async def get_session_history(pm_email: str, limit: int = 15) -> list[dict]:
    """Get recent sessions for a PM, sorted by start_time descending."""
    ddb = _get_dynamodb_resource()
    table = ddb.Table(TABLE_NAME)

    try:
        resp = table.query(
            IndexName="pm_email-start_time-index",
            KeyConditionExpression="pm_email = :email",
            ExpressionAttributeValues={":email": pm_email},
            ScanIndexForward=False,
            Limit=limit,
        )
        return [
            {
                "session_id": item["session_id"],
                "title": item.get("title", "New conversation"),
                "start_time": item.get("start_time", ""),
                "status": item.get("status", ""),
            }
            for item in resp.get("Items", [])
        ]
    except Exception:
        return []


async def get_session_messages(session_id: str) -> list[dict] | None:
    """Get messages for a specific session (for replay)."""
    ddb = _get_dynamodb_resource()
    table = ddb.Table(TABLE_NAME)

    try:
        resp = table.get_item(Key={"session_id": session_id})
        item = resp.get("Item")
        if not item:
            return None
        return item.get("messages", [])
    except Exception:
        return None
