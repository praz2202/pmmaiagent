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

from session.models import PMAgentState, SessionRecord

TABLE_NAME = "pmm-agent-sessions"


def _get_dynamodb_resource():
    """Get DynamoDB resource — local or prod based on DYNAMODB_ENDPOINT."""
    endpoint = os.getenv("DYNAMODB_ENDPOINT")
    region = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")

    if endpoint:
        # Local DynamoDB — needs dummy credentials
        return boto3.resource(
            "dynamodb",
            region_name=region,
            endpoint_url=endpoint,
            aws_access_key_id="local",
            aws_secret_access_key="local",
        )
    else:
        # Production — uses real AWS credentials
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
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    # Wait for table to be active
    ddb.Table(TABLE_NAME).wait_until_exists()


async def save_session_record(state: PMAgentState, status: str) -> None:
    """Build SessionRecord from live state and write to DynamoDB.
    Called once when session ends (PM clicks Restart or session completes).
    """
    record = SessionRecord(
        session_id=state.session_id,
        pm_name=state.pm_name,
        pm_email=state.pm_context.email if state.pm_context else "",
        start_time=state.start_time or "",
        end_time=datetime.now(timezone.utc).isoformat(),
        status=status,
        tool_calls=state.tool_calls,
    )

    # DynamoDB write (sync — runs in thread pool if needed)
    ddb = _get_dynamodb_resource()
    table = ddb.Table(TABLE_NAME)
    table.put_item(Item=record.model_dump())
