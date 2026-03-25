"""
services/orchestration/tools/api_client.py

Shared API client for skill tools.
Local dev: makes direct httpx calls (no Lambda needed).
Production: invokes pmm-skill-client Lambda.

Tools call `api_call()` instead of `lambda_client.invoke_skill_lambda()`.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
import logfire

from settings import APP_ENV

logfire.instrument_httpx()


async def aha_api_call(method: str, path: str, params: dict | None = None) -> Any:
    """Call the Aha API. Direct httpx in local dev, Lambda in prod."""
    api_key = os.getenv("AHA_API_KEY")
    base_url = "https://egain.aha.io/api/v1"

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method,
            f"{base_url}{path}",
            params=params or {},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=30,
        )
        if resp.status_code == 404:
            return {"error": f"Not found: {path}. The ID may not exist in Aha."}
        resp.raise_for_status()
        if not resp.text or not resp.text.strip():
            return {}
        return resp.json()


# eGain On-Behalf-Of token cache (keyed by egain_username)
_egain_token_cache: dict[str, dict] = {}

EGAIN_OBO_TOKEN_URL = "https://api.egain.cloud/core/authmgr/v4/oauth2/v2.0/onbehalfof/token?tenantId=TMPROD11055874&user_type=user"
EGAIN_OBO_SCOPE = "https://tmprod11055874int.onmicrosoft.com/12bf53d5-dc02-429f-bc2b-d8707c60e69d/knowledge.portalmgr.onbehalfof.read"


async def _get_egain_obo_token(egain_username: str) -> str:
    """Get eGain On-Behalf-Of token for a specific user. Cached."""
    import time

    cached = _egain_token_cache.get(egain_username)
    if cached and cached.get("expires_at", 0) > time.time():
        return cached["token"]

    client_id = os.getenv("EGAIN_CLIENT_ID")
    client_secret = os.getenv("EGAIN_CLIENT_SECRET")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            EGAIN_OBO_TOKEN_URL,
            data={
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": EGAIN_OBO_SCOPE,
                "subject_username": egain_username,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        _egain_token_cache[egain_username] = {
            "token": token,
            "expires_at": time.time() + expires_in - 60,  # refresh 60s before expiry
        }
        return token


async def egain_api_call(
    method: str,
    path: str,
    params: dict | None = None,
    egain_username: str | None = None,
) -> Any:
    """Call the eGain Knowledge API using On-Behalf-Of token.
    Requires egain_username to get a user-scoped token.
    """
    if not egain_username:
        raise ValueError("egain_username is required for eGain API calls")

    token = await _get_egain_obo_token(egain_username)
    base_url = "https://api.egain.cloud/knowledge/portalmgr/v4"

    async with httpx.AsyncClient() as client:
        resp = await client.request(
            method,
            f"{base_url}{path}",
            params=params or {},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Accept-Language": "en-US",
            },
            timeout=30,
        )
        if resp.status_code == 404:
            return {"error": f"Not found: {path}. The resource may not exist."}
        resp.raise_for_status()
        if not resp.text or not resp.text.strip():
            return {}
        return resp.json()
