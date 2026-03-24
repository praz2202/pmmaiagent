"""
services/orchestration/tools/deps.py

AgentDeps: runtime dependency container for the PMM AI Agent.
Never serialised to Redis. Reconstructed each HTTP request from PMAgentState + config.

Passed to agent via: agent.run(prompt, deps=agent_deps)
Accessed in tools via: ctx.deps.lambda_client, ctx.deps.pm_context, etc.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

import boto3
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from settings import PROVIDERS, DEFAULT_PROVIDER, DEFAULT_MODEL_SETTINGS
from session.models import PMContext


class LambdaClient:
    """Thin wrapper around boto3 Lambda client for invoking skill Lambdas.
    One instance shared across all sessions (process-level singleton).
    """
    def __init__(self):
        self._client = boto3.client(
            "lambda",
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-west-2"),
        )

    async def invoke_skill_lambda(self, lambda_name: str, payload: dict) -> dict:
        """Invoke the pmm-skill-client Lambda synchronously (via thread pool).
        Returns the parsed response body. Raises on non-200 status.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.invoke(
                FunctionName=lambda_name,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload).encode(),
            ),
        )
        result = json.loads(response["Payload"].read())
        if result.get("statusCode") != 200:
            raise RuntimeError(f"Lambda {lambda_name} error: {result}")
        return result["body"]


@dataclass
class AgentDeps:
    """
    Injected into the PMM AI Agent via RunContext[AgentDeps].
    All tool functions access this via ctx.deps.

    - lambda_client:  invokes skill Lambdas (Aha, eGain API calls)
    - llm_model:      PydanticAI OpenAIModel configured from PROVIDERS
    - model_settings: {"extra_body": {"reasoning_effort": "low"}}
    - pm_context:     parsed PM data from company-context.md
    - session_id:     for session tracking and DynamoDB history
    """
    lambda_client: LambdaClient
    llm_model: OpenAIModel
    model_settings: dict
    pm_context: PMContext
    session_id: str


# ── Process-level singletons ─────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_lambda_client() -> LambdaClient:
    """One LambdaClient for the entire process. Stateless."""
    return LambdaClient()


@lru_cache(maxsize=1)
def _get_llm_model() -> OpenAIModel:
    """Build PydanticAI OpenAIModel from the configured provider.
    Cached — one model instance for all sessions.
    """
    provider = PROVIDERS[DEFAULT_PROVIDER]
    api_key = _resolve_llm_api_key(provider)
    openai_provider = OpenAIProvider(base_url=provider["base_url"], api_key=api_key)
    return OpenAIModel(provider["model"], provider=openai_provider)


def _resolve_llm_api_key(provider: dict) -> str:
    """Env var first (local dev), then Secrets Manager (prod)."""
    override = os.getenv(provider["api_key_env"])
    if override:
        return override

    sm = boto3.client(
        "secretsmanager",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-west-2"),
    )
    secret = json.loads(
        sm.get_secret_value(SecretId=provider["credentials_secret"])["SecretString"]
    )
    return secret["api_key"]


# ── Per-session factory ──────────────────────────────────────────────────────

def build_deps(
    pm_context: PMContext,
    session_id: str,
) -> AgentDeps:
    """Build AgentDeps for one session turn.
    Called by FastAPI endpoints before running the agent.
    """
    return AgentDeps(
        lambda_client=_get_lambda_client(),
        llm_model=_get_llm_model(),
        model_settings=DEFAULT_MODEL_SETTINGS,
        pm_context=pm_context,
        session_id=session_id,
    )
