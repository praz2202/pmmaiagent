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

from settings import APP_ENV


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
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


# eGain OAuth token cache
_egain_token_cache: dict[str, Any] = {}


async def _get_egain_token() -> str:
    """Get eGain OAuth token (Client Credentials flow). Cached."""
    if "token" in _egain_token_cache:
        return _egain_token_cache["token"]

    client_id = os.getenv("EGAIN_CLIENT_ID")
    client_secret = os.getenv("EGAIN_CLIENT_SECRET")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://login.egain.cloud/global/f51302dd-7036-41b5-b619-e1a52a67c780/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.egain.cloud/auth/.default",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        token = resp.json()["access_token"]
        _egain_token_cache["token"] = token
        return token


async def egain_api_call(method: str, path: str, params: dict | None = None) -> Any:
    """Call the eGain Knowledge API. Uses OAuth Client Credentials token."""
    token = await _get_egain_token()
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
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
