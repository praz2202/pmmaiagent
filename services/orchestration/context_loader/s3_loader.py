"""
services/orchestration/context_loader/s3_loader.py

Loads company-context.md from S3 (prod) or local file (dev) and parses it
into typed PMContext structs. The raw Markdown is consumed here — never
injected into prompts directly.

Process-level cache with 5-min TTL: all concurrent sessions share one parse.
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any

import boto3

from session.models import AhaMapping, PMContext, PortalContext, PortalTopic


# ── Cache ────────────────────────────────────────────────────────────────────

_cache: dict[str, Any] = {}
_CACHE_TTL = 300  # 5 minutes


def invalidate_cache() -> None:
    """Called by /internal/context/invalidate when S3 is updated."""
    _cache.clear()


# ── Public API ───────────────────────────────────────────────────────────────

def load_company_context(pm_name: str) -> PMContext:
    """Load and parse company-context.md; return PMContext for this PM.
    Looks up PM by name (must match the frontend dropdown exactly).
    """
    raw = _get_raw_md()
    all_pms = _parse_all_pm_contexts(raw)

    # Find PM by name (case-insensitive match)
    for ctx in all_pms.values():
        if ctx.name.lower() == pm_name.lower():
            return ctx

    available = [ctx.name for ctx in all_pms.values()]
    raise ValueError(f"PM name '{pm_name}' not found. Available: {available}")


# ── Raw Markdown loading ─────────────────────────────────────────────────────

def _get_raw_md() -> str:
    now = time.monotonic()
    if "raw" in _cache:
        ts, val = _cache["raw"]
        if now - ts < _CACHE_TTL:
            return val

    raw = _fetch_raw()
    _cache["raw"] = (now, raw)
    return raw


def _fetch_raw() -> str:
    """Fetch from S3 in prod, local file in dev."""
    app_env = os.getenv("APP_ENV", "local")

    if app_env == "local":
        # Read from local file
        local_path = Path(__file__).parents[3] / "context" / "company-context.md"
        return local_path.read_text(encoding="utf-8")
    else:
        # Read from S3
        bucket = os.environ["CONTEXT_BUCKET"]
        s3 = boto3.client("s3")
        return s3.get_object(Bucket=bucket, Key="company-context.md")["Body"].read().decode()


# ── Parsing ──────────────────────────────────────────────────────────────────

def _parse_all_pm_contexts(raw_md: str) -> dict[str, PMContext]:
    """Parse the Markdown into a dict keyed by PM email."""
    pm_rows = _parse_pm_ownership_table(raw_md)
    aha_mappings = _parse_aha_mappings_table(raw_md)
    portal_context = _parse_portal_context(raw_md)
    cadence_rules = _parse_cadence_rules(raw_md)
    docs_impacted_rules = _parse_documents_impacted(raw_md)

    result = {}
    for row in pm_rows:
        email = row["email"].strip()
        products = [p.strip() for p in row["products"].split(",")]
        result[email] = PMContext(
            pm_id=email.split("@")[0],
            name=row["name"].strip(),
            email=email,
            owned_products=products,
            reports_to=row.get("reports_to", "").strip() or None,
            aha_mappings={k: v for k, v in aha_mappings.items() if k in products},
            portal_context=portal_context,
            release_cadence_rules=cadence_rules,
            documents_impacted_rules=docs_impacted_rules,
        )
    return result


def _parse_pm_ownership_table(raw_md: str) -> list[dict]:
    """Parse the PM to Product Ownership table."""
    rows = []
    in_table = False
    for line in raw_md.splitlines():
        if "## PM to Product Ownership" in line:
            in_table = True
            continue
        if in_table and line.startswith("##"):
            break
        if in_table and line.startswith("|") and "---|" not in line and "PM Name" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 4:
                rows.append({
                    "name": cols[0],
                    "email": cols[1],
                    "products": cols[2],
                    "role": cols[3] if len(cols) > 3 else "",
                    "reports_to": cols[4] if len(cols) > 4 else "",
                })
    return rows


def _parse_aha_mappings_table(raw_md: str) -> dict[str, AhaMapping]:
    """Parse the Aha Product Mappings table."""
    mappings = {}
    in_table = False
    for line in raw_md.splitlines():
        if "## Aha Product Mappings" in line:
            in_table = True
            continue
        if in_table and line.startswith("##"):
            break
        if in_table and line.startswith("|") and "---|" not in line and "Product Name" not in line:
            cols = [c.strip().strip("`") for c in line.strip("|").split("|")]
            if len(cols) >= 5:
                code = cols[1]
                release_tracking = cols[4] if len(cols) > 4 else ""
                is_aia = "version tag" in release_tracking.lower() or "AIA" in release_tracking
                mappings[code] = AhaMapping(
                    product=cols[0],
                    aha_product_key=code,
                    release_field_type="aia_version_tag" if is_aia else "standard_release",
                    aia_version_prefix="AIA" if is_aia else None,
                )
    return mappings


def _parse_portal_context(raw_md: str) -> PortalContext:
    """Parse the eGain Portal Context section into a PortalContext."""
    portal_short_id = ""
    topics: list[PortalTopic] = []

    in_section = False
    current_product = None

    for line in raw_md.splitlines():
        if "## eGain Portal Context" in line:
            in_section = True
            continue
        if in_section and line.startswith("## ") and "Portal Context" not in line:
            break
        if not in_section:
            continue

        # Extract portal short ID
        if "Portal Short ID:" in line:
            portal_short_id = line.split(":", 1)[1].strip().strip("`")

        # Detect topic ID table rows
        if in_section and line.startswith("|") and "---|" not in line and "Topic" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 3:
                # Topic ID table: | Topic | Topic ID | Product | Notes |
                try:
                    topic_id = cols[1].strip()
                    # Only add if topic_id looks like a number
                    if topic_id.isdigit():
                        topics.append(PortalTopic(
                            name=cols[0].strip(),
                            topic_id=topic_id,
                            product=cols[2].strip() if len(cols) > 2 else None,
                            notes=cols[3].strip() if len(cols) > 3 else None,
                        ))
                except (IndexError, ValueError):
                    pass

    return PortalContext(portal_short_id=portal_short_id, topics=topics)


def _parse_cadence_rules(raw_md: str) -> str:
    """Parse the Release Tracking Rules section as a text block."""
    match = re.search(
        r"## Release Tracking Rules\n(.*?)(?=\n##|\Z)", raw_md, re.DOTALL
    )
    return match.group(1).strip()[:800] if match else ""


def _parse_documents_impacted(raw_md: str) -> str:
    """Parse the Documents Impacted Attribute section as a text block.
    Returned as-is — injected into agent prompts for feature filtering.
    """
    match = re.search(
        r"## Documents Impacted Attribute\n(.*?)(?=\n---|\n##|\Z)", raw_md, re.DOTALL
    )
    return match.group(1).strip()[:1500] if match else ""
