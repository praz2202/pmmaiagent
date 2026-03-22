# PMM AI Agent — Implementation Guide

**Project:** eGain Product Marketing Manager (PMM) AI Agent  
**Version:** 2.0  
**Document type:** Sequential build guide — follow steps top to bottom  
**Architecture reference:** `pmm-ai-agent-architecture.md`  
**Repository map:** `REPO.md` — read before navigating any file in the codebase

---

## How to use this guide

Every step in this guide is executable in order. Each step has:

- **What you're building** — one concrete artifact (a file, a command, a running service)
- **The exact commands or code** — copy-paste ready
- **A checkpoint** — what to verify before moving to the next step

Do not skip a checkpoint. If it fails, fix it before continuing — later steps assume earlier ones are working.

**Time estimate per section:**

| Section | Time |
|---|---|
| Section 0 — Prerequisites | 1–2 hours (mostly waiting for AWS provisioning) |
| Section 1 — Repository scaffold | 20 minutes |
| Section 2 — AWS infrastructure | 1–2 hours |
| Section 3 — Skill folders | 2–3 hours |
| Section 4 — Core service code | 4–6 hours |
| Section 5 — Graph nodes | 4–8 hours |
| Section 6 — FastAPI layer | 1–2 hours |
| Section 7 — Dockerfile + Lambda | 1 hour |
| Section 8 — Test suite | 2–3 hours |
| Section 9 — Deploy to dev | 1–2 hours |
| Section 9b — Observability | 30 minutes |
| Section 10 — Frontend | 1 hour |
| Section 11 — CI/CD and production | 30 minutes |
| Section 14 — Extension guide | reference |

---

## Section 0 — Prerequisites

Before writing a single line of code, verify you have everything below. Attempting to build without these in place means hitting blockers mid-build.

### Step 0.1 — Local machine requirements

Install the following tools and verify each version:

```bash
# Python 3.11 or higher
python3 --version            # must show 3.11.x or 3.12.x

# Docker Desktop
docker --version             # must show 24.x or higher
docker compose version       # must show v2.x

# AWS CLI v2
aws --version                # must show aws-cli/2.x

# Terraform
terraform -version           # must show 1.7 or higher

# uv (fast Python package manager)
uv --version                 # must show 0.4 or higher
# Install if missing:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Git
git --version
```

**Checkpoint 0.1:** All six commands return version numbers without errors.

---

### Step 0.2 — AWS account setup

You need an AWS account with an IAM user or role that has the following permissions. Create a dedicated IAM user named `pmm-agent-deployer` rather than using root credentials.

**Required IAM permissions:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:*",
        "ecs:*",
        "ec2:*",
        "elasticache:*",
        "s3:*",
        "secretsmanager:*",
        "logs:*",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:PassRole",
        "lambda:*",
        "cloudfront:*"
      ],
      "Resource": "*"
    }
  ]
}
```

Configure the CLI profile:

```bash
aws configure --profile pmm-agent-dev
# Enter: Access Key ID, Secret Access Key, region (us-east-1), output format (json)

# Verify it works
aws sts get-caller-identity --profile pmm-agent-dev
# Should return your account ID and IAM user ARN
```

**Checkpoint 0.2:** `aws sts get-caller-identity` returns your account ID. Note the account ID — you'll need it in Step 2.

---

### Step 0.3 — External API access

Before any code can run, you need these credentials. Get them from the respective systems and have them ready — they get stored in AWS Secrets Manager in Step 2.

**Aha API key:**
- Log in to `egain.aha.io` → Account Settings → Developer → API Keys
- Create a **service account key** (not your personal key — this runs in production)
- Note it down; you will never see it again after closing the dialog

**eGain Knowledge API v4 credentials:**
- Get a `client_app` and `client_secret` for on-behalf-of-customer auth from your eGain admin
- Confirm the base URL of the Knowledge API (e.g. `apidev.egain.com`)
- Verify the service account has read access to portal articles

**Anthropic API key:**
- Go to `console.anthropic.com` → API Keys → Create Key
- Name it `pmm-agent-prod`
- Note it down

**AHA subdomain:**
- Your Aha URL is `https://egain.aha.io` → subdomain is `egain`

**Checkpoint 0.3:** You have all four values written down (not in any file yet):
- Aha API key
- eGain username + password + host
- Anthropic API key
- Aha subdomain (`egain`)

---

## Section 1 — Repository Scaffold

### Step 1.1 — Create the repo

```bash
# Create the repository
mkdir pmm-ai-agent && cd pmm-ai-agent
git init
git checkout -b main

# Create the full directory structure in one command
mkdir -p \
  context \
  config/skills/aha/scripts \
  config/skills/aha/references \
  config/skills/egain/scripts \
  config/skills/egain/references \
  config/skills/company-context/references \
  docs \
  frontend \
  infrastructure/terraform/modules/{networking,redis,s3,secrets,ecs,lambda} \
  infrastructure/scripts \
  infrastructure/git-hooks \
  services/orchestration/context_loader \
  services/orchestration/graph/nodes \
  services/orchestration/session \
  services/orchestration/tools \
  lambdas/context-refresher \
  tests/unit/{aha,egain,orchestration,tools,lambdas} \
  tests/functional \
  tests/integration \
  tests/smoke \
  tests/e2e \
  tests/fixtures
```

**Checkpoint 1.1:** `find . -type d | sort` shows all directories. No errors.

---

### Step 1.2 — Create root config files

```bash
# .gitignore
cat > .gitignore << 'EOF'
.env.local
.env.dev
.env.prod
__pycache__/
*.pyc
.pytest_cache/
htmlcov/
.coverage
*.egg-info/
dist/
build/
.terraform/
terraform.tfstate*
*.tfvars
!terraform.tfvars.example
.DS_Store
EOF

# .env.example — committed to repo, safe defaults
cat > .env.example << 'EOF'
APP_ENV=local
LOG_LEVEL=debug

# Redis (local Docker)
REDIS_URL=redis://localhost:6379

# Aha
AHA_SUBDOMAIN=egain
AHA_API_KEY_OVERRIDE=          # set locally to skip Secrets Manager

# eGain (read-only Knowledge API v4)
EGAIN_API_HOST=apidev.egain.com
EGAIN_CLIENT_APP_OVERRIDE=     # set locally to skip Secrets Manager
EGAIN_CLIENT_SECRET_OVERRIDE=  # set locally to skip Secrets Manager

# LLM Providers (set the one matching DEFAULT_PROVIDER in config.py)
GEMINI_API_KEY=                # default provider — set locally to skip Secrets Manager
CLAUDE_API_KEY=                # Anthropic — set if switching DEFAULT_PROVIDER
OPENAI_API_KEY=                # OpenAI — set if switching DEFAULT_PROVIDER

# AWS
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=pmm-agent-dev

# S3 context bucket
CONTEXT_BUCKET=egain-pmm-agent-context-dev

# Frontend
FRONTEND_ORIGIN_DEV=http://localhost:3000
EOF

# Copy and fill in your local values
cp .env.example .env.local
echo "Edit .env.local and add your API keys now"
```

Edit `.env.local` and fill in the four `_OVERRIDE` values you collected in Step 0.3.

```bash
# pyproject.toml
cat > pyproject.toml << 'EOF'
[project]
name = "pmm-ai-agent"
version = "1.0.0"
requires-python = ">=3.11"

[tool.uv.workspace]
members = [
  "services/orchestration",
  "lambdas/context-refresher",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
  "unit: fully mocked, no network",
  "functional: real graph transitions, LLM mocked",
  "integration: real dev APIs, requires --run-live",
  "smoke: post-deploy health checks",
  "e2e: full session flow via HTTP",
]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = false
EOF
```

```bash
# services/orchestration/requirements.txt
cat > services/orchestration/requirements.txt << 'EOF'
pydantic-ai>=0.1.0
pydantic-graph>=0.1.0
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
redis[asyncio]>=5.0.0
boto3>=1.34.0
httpx>=0.27.0
python-dotenv>=1.0.0
EOF

# services/orchestration/requirements-dev.txt
cat > services/orchestration/requirements-dev.txt << 'EOF'
pytest>=8.0
pytest-asyncio>=0.23
pytest-cov>=5.0
ruff>=0.5.0
mypy>=1.10.0
EOF
```

```bash
# Install everything
cd services/orchestration
uv pip install -r requirements.txt -r requirements-dev.txt
cd ../..
```

**Checkpoint 1.2:** `python -c "import pydantic_ai, fastapi, redis, httpx; print('all imports OK')"` prints successfully.

---

### Step 1.3 — docker-compose for local dev

```yaml
# docker-compose.yml
```

Create `docker-compose.yml` with this content:

```yaml
services:
  orchestration:
    build:
      context: services/orchestration
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env.local
    environment:
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./config:/app/config:ro
      - ./context:/app/context:ro
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
```

**Checkpoint 1.3:** `docker compose up redis -d` starts Redis. `docker compose ps` shows it healthy. `redis-cli ping` returns `PONG`.

---

### Step 1.4 — Install git hooks

```bash
# infrastructure/git-hooks/pre-push
cat > infrastructure/git-hooks/pre-push << 'EOF'
#!/bin/bash
set -e
echo "→ Linting..."
ruff check services/ tests/
echo "→ Unit tests..."
pytest tests/unit/ -q --tb=short
echo "✅ Pre-push checks passed"
EOF

chmod +x infrastructure/git-hooks/pre-push

# Install
cat > infrastructure/scripts/install-hooks.sh << 'EOF'
#!/bin/bash
cp infrastructure/git-hooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
echo "Git hooks installed"
EOF

bash infrastructure/scripts/install-hooks.sh
```

**Checkpoint 1.4:** `cat .git/hooks/pre-push` shows the script content.

---

## Section 2 — AWS Infrastructure

Build AWS infrastructure before writing application code. The app needs the S3 bucket, Redis endpoint, and Secrets Manager ARNs at runtime.

### Step 2.1 — Bootstrap Secrets Manager entries

Create the secret entries now so you can reference their ARNs in all subsequent Terraform config. Set real values immediately — you have them from Step 0.3.

```bash
export AWS_PROFILE=pmm-agent-dev
export AWS_DEFAULT_REGION=us-east-1
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Create secrets (replace placeholders with your real values)
aws secretsmanager create-secret \
  --name "pmm-agent/aha-api-key" \
  --secret-string "{\"api_key\":\"YOUR_AHA_KEY_HERE\"}"

aws secretsmanager create-secret \
  --name "pmm-agent/egain-credentials" \
  --secret-string "{\"client_app\":\"YOUR_EGAIN_CLIENT_APP\",\"client_secret\":\"YOUR_EGAIN_CLIENT_SECRET\"}"

aws secretsmanager create-secret \
  --name "pmm-agent/gemini-api-key" \
  --secret-string "{\"api_key\":\"YOUR_GEMINI_KEY_HERE\"}"

aws secretsmanager create-secret \
  --name "pmm-agent/anthropic-api-key" \
  --secret-string "{\"api_key\":\"YOUR_ANTHROPIC_KEY_HERE\"}"

aws secretsmanager create-secret \
  --name "pmm-agent/openai-api-key" \
  --secret-string "{\"api_key\":\"YOUR_OPENAI_KEY_HERE\"}"

echo "Secrets created. ARNs:"
aws secretsmanager list-secrets --query "SecretList[?starts_with(Name,'pmm-agent')].ARN" --output text
```

**Checkpoint 2.1:** Five secret ARNs printed. Verify in AWS Console → Secrets Manager that all five exist.

---

### Step 2.2 — Provision S3 context bucket

```bash
BUCKET_NAME="egain-pmm-agent-context-${ACCOUNT_ID}"

aws s3api create-bucket \
  --bucket "${BUCKET_NAME}" \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket "${BUCKET_NAME}" \
  --versioning-configuration Status=Enabled

# Block public access
aws s3api put-public-access-block \
  --bucket "${BUCKET_NAME}" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket "${BUCKET_NAME}" \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'

echo "S3 bucket: ${BUCKET_NAME}"
# Save this for .env.local
```

Update `.env.local`:
```
CONTEXT_BUCKET=egain-pmm-agent-context-YOURACCOUNTID
```

**Checkpoint 2.2:** `aws s3 ls s3://${BUCKET_NAME}` returns empty (no error). Versioning shows `Enabled`.

---

### Step 2.3 — Provision ECR repository

```bash
aws ecr create-repository \
  --repository-name pmm-orchestration \
  --region us-east-1

ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"
echo "ECR registry: ${ECR_REGISTRY}/pmm-orchestration"
```

**Checkpoint 2.3:** `aws ecr describe-repositories --repository-names pmm-orchestration` returns the repository URI.

---

### Step 2.4 — Provision Terraform infrastructure (VPC, Redis, ECS)

```bash
# infrastructure/terraform/terraform.tfvars.example
cat > infrastructure/terraform/terraform.tfvars.example << 'EOF'
aws_account_id = "YOUR_ACCOUNT_ID"
aws_region     = "us-east-1"
env            = "dev"
vpc_cidr       = "10.0.0.0/16"
EOF

cp infrastructure/terraform/terraform.tfvars.example infrastructure/terraform/terraform.tfvars
# Edit terraform.tfvars and set your account ID

cd infrastructure/terraform
terraform init

# Provision in dependency order
terraform apply -target=module.networking -auto-approve
terraform apply -target=module.redis -auto-approve
terraform apply -target=module.ecs -auto-approve
terraform apply -target=module.lambda -auto-approve

# Note the outputs
terraform output redis_endpoint
terraform output public_alb_dns_name
terraform output ecs_cluster_name
cd ../..
```

Update `.env.local` with the Redis endpoint:
```
REDIS_URL=redis://REDIS_ENDPOINT_FROM_TERRAFORM:6379
```

**Checkpoint 2.4:** `terraform output` shows `redis_endpoint`, `public_alb_dns_name`, `ecs_cluster_name` without errors. In AWS Console, verify ECS cluster exists and Redis cluster is `available`.

---

## Section 3 — Skill Folders

Write the three skill folders. These are the heart of what the agent knows — bad content here produces bad agent decisions. Take time on these.

### Step 3.1 — Aha skill — `SKILL.md`

```bash
cat > config/skills/aha/SKILL.md << 'SKILL'
---
name: aha
description: >
  Fetches release features and specs from Aha for eGain products (AIA, ECAI, ECKN, ECAD).
  Use when a PM needs release context: feature lists, specs, attachments, Jira URLs, or
  component mappings. Trigger on: release documentation, feature specs, release notes planning.
---

# Aha Skill

## How the tools work together

- `aha_list_releases` — returns release summaries for a product (use for PM selection)
- `aha_get_release_features` — returns full feature details in one call (description, custom_fields, tags, attachments)
- `aha_get_feature_attachments` — downloads image attachments for a specific feature
- `aha_get_components` — returns the component tree for a product

AIA uses version tags (`AIA 1.2.0`), not release IDs. All other products use standard release IDs.
See [references/aia-releases.md](references/aia-releases.md) for AIA-specific fetch patterns.

## Filtering features for release notes

After fetching features, check `custom_fields[name="documents_impacted"].value`.
If it contains "release notes" (case-insensitive), the feature needs a portal article update.
See [references/filtering.md](references/filtering.md) for field paths and edge cases.

## Cross-product: ECKN + ECAI

ECKN features may have ECAI component dependencies. Check component tags —
if an ECAI component is present, flag it in the plan for Prasanth Sai or Carlos España review.

## Gotchas

- AIA does NOT use the Release field — `aha_list_releases` returns nothing useful for AIA. Use tags instead.
- Aha CDN image URLs require Aha auth — NEVER embed them in portal HTML. Download via `aha_get_feature_attachments` first.
- `documents_impacted` filter is case-insensitive — "Release Notes" and "release notes" both match.
- Rate limit is 100 req/min shared across ALL concurrent sessions — 429 errors are expected under load, surface to PM.
- Jira URL has two field paths: try `custom_fields["jira_url"]` first, fall back to `integration_fields["url"]`. If both null, note it but don't block.
- Always pass release_id (not release name) to `aha_get_release_features` for standard products.

See [references/api.md](references/api.md) for full field path details and API reference.
SKILL
```

**Checkpoint 3.1:** `cat config/skills/aha/SKILL.md` — file exists, YAML frontmatter is at top.

---

### Step 3.2 — Aha skill — `tools.py`

```python
"""
config/skills/aha/tools.py

Aha tool functions — imported directly by agent nodes.
Each function has typed params, a docstring (used as the tool description),
and calls ctx.deps.lambda_client.invoke_skill_lambda() to hit the Aha API.
"""
from __future__ import annotations

from typing import Any
from pydantic_ai import RunContext
from tools.deps import AgentDeps

AHA_API_CONFIG = {
    "name": "aha",
    "base_url": "https://{subdomain}.aha.io/api/v1",
    "auth": {
        "type": "basic",
        "credentials_secret": "pmm-agent/aha-api-key",
        "secret_field": "api_key",
    },
    "rate_limit": {
        "requests_per_minute": 100,
        "note": "No client-side rate limiter — 429 errors propagate to the agent",
    },
}


async def aha_list_releases(ctx: RunContext[AgentDeps], product_key: str) -> Any:
    """List active releases for an Aha product. Returns releases with status
    'in_progress' or 'planned' only. Use first to show the PM which releases
    are available (summary only — for selection, not full details).
    For AIA, this is not needed — AIA uses version tags, not release IDs.

    Args:
        product_key: Aha product key: 'AIA', 'ECAI', 'ECKN', or 'ECAD'.
    """
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": f"/products/{product_key}/releases",
        "params": {"product_key": product_key},
        "api_config": AHA_API_CONFIG,
    })


async def aha_get_release_features(
    ctx: RunContext[AgentDeps],
    release_id: str | None = None,
    product_key: str | None = None,
    tag: str | None = None,
    fields: str = "name,description,custom_fields,tags,attachments",
) -> Any:
    """Get all features for a release with FULL details inline (description,
    custom_fields, tags, attachments). Uses the Aha `fields` query parameter
    to return everything in a single API call — no per-feature detail fetches.
    For standard products (ECAI, ECKN, ECAD): pass release_id.
    For AIA: pass product_key + tag instead (AIA uses version tags, not releases).

    Args:
        release_id: Aha release ID from aha_list_releases. Required for ECAI/ECKN/ECAD.
        product_key: Aha product key. Required for AIA tag-based fetch.
        tag: AIA version tag, e.g. 'AIA 1.2.0'. Only for AIA.
        fields: Comma-separated fields to include. Default returns full details.
    """
    path = f"/releases/{release_id}/features" if release_id else f"/products/{product_key}/features"
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": path,
        "params": {"release_id": release_id, "product_key": product_key, "tag": tag, "fields": fields},
        "api_config": AHA_API_CONFIG,
    })


async def aha_get_feature_attachments(ctx: RunContext[AgentDeps], feature_id: str) -> Any:
    """Get image attachments for a feature. Returns download URLs for inline images
    in the feature description. Only image/* content types are returned.
    Download these images — never link directly to Aha CDN URLs.

    Args:
        feature_id: Feature ID, e.g. 'ECAI-123'.
    """
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": f"/features/{feature_id}/attachments",
        "params": {"feature_id": feature_id},
        "api_config": AHA_API_CONFIG,
    })


async def aha_get_components(ctx: RunContext[AgentDeps], product_key: str) -> Any:
    """Get the component tree for an Aha product. Used to understand which part
    of the product a feature belongs to when planning documentation structure.

    Args:
        product_key: Aha product key: 'AIA', 'ECAI', 'ECKN', or 'ECAD'.
    """
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": f"/products/{product_key}/components",
        "params": {"product_key": product_key},
        "api_config": AHA_API_CONFIG,
    })


AHA_TOOLS = [
    aha_list_releases,
    aha_get_release_features,
    aha_get_feature_attachments,
    aha_get_components,
]
```

**Checkpoint 3.2:** `python -c "from config.skills.aha.tools import AHA_TOOLS; print(len(AHA_TOOLS), 'tools defined')"` prints `4 tools defined`.

---

### Step 3.3 — Aha skill — `scripts/aha_client.py` (optional helpers)

Create `config/skills/aha/scripts/aha_client.py`. This file contains Aha-specific helpers (AIA path resolution) that the generic `pmm-skill-client` Lambda can import. Auth is handled by the Lambda based on `AHA_API_CONFIG` from `tools.py` — not by this file.

```python
"""
config/skills/aha/scripts/aha_client.py

Aha-specific helpers used by pmm-skill-client Lambda.
Auth is NOT handled here — it's config-driven from AHA_API_CONFIG in tools.py.
"""
from __future__ import annotations


def resolve_aha_path(path: str, params: dict) -> str:
    """Handle AIA tag-based fetch: switch from /releases/{id}/features to /products/{key}/features."""
    if "product_key" in params and "tag" in params and "release_id" not in params:
        return f"/products/{params['product_key']}/features"
    return path
```

**Checkpoint 3.3:** `python config/skills/aha/scripts/aha_client.py` runs without import errors.

---

### Step 3.4 — Aha skill — `references/api.md`

```bash
cat > config/skills/aha/references/api.md << 'REF'
# Aha API Reference

## Product keys
  AIA   → egain.aha.io/products/AIA
  ECAI  → egain.aha.io/products/ECAI
  ECKN  → egain.aha.io/products/ECKN
  ECAD  → egain.aha.io/products/ECAD

## Feature custom field paths (JSONPath notation)
  documents_impacted:
    feature.custom_fields[?(@.name=="documents_impacted")].value
  jira_url (primary):
    feature.custom_fields[?(@.name=="jira_url")].value
  jira_url (fallback):
    feature.integration_fields[?(@.name=="url")].value

## AIA version tag format
  feature.tags[]  — look for any tag matching pattern: AIA \d+\.\d+\.\d+
  Examples: "AIA 1.2.0", "AIA 2.0.0"

## Release name formats
  Standard (ECAI, ECKN, ECAD): "YY.MM"  e.g. "25.03"
  AIA:                          "AIA x.x.x"  e.g. "AIA 1.2.0"

## Release status filter
  Only return: "in_progress", "planned"
  Skip:        "shipped", "archived", "will_not_ship"

## Fields parameter (inline detail fetch)
  Use ?fields=name,description,custom_fields,tags,attachments on list endpoints
  to get full feature details in a single API call. No per-feature detail fetches needed.
  Example: GET /releases/{id}/features?fields=name,description,custom_fields,tags,attachments
  Example: GET /products/AIA/features?tag=AIA+1.2.0&fields=name,description,custom_fields,tags,attachments

## Attachment download
  attachment.download_url — requires Basic auth header (handled by aha_client Lambda)
  Download and base64-encode images before referencing in portal content.

## Rate limit
  100 req/min per API key — shared across all concurrent user sessions.
  No client-side rate limiter — if Aha returns 429, the Lambda propagates
  the error and the agent surfaces it to the PM.
REF

# Aha progressive disclosure — additional reference files
cat > config/skills/aha/references/aia-releases.md << 'REF'
# AIA Release Fetch Pattern

AIA (AI Agent) does NOT use the standard Aha Release field.
Instead, individual features are tagged with version strings.

## How AIA versioning works

- Features are tagged with version strings: `AIA 1.0.0`, `AIA 1.2.0`, `AIA 2.0.0`
- Tag format regex: `AIA \d+\.\d+\.\d+`
- All AIA features live at: egain.aha.io/products/AIA/feature_cards

## Fetching AIA features

Use `aha_get_release_features(product_key="AIA", tag="AIA x.x.x")`.
Do NOT use `aha_list_releases` for AIA — it returns standard releases which AIA doesn't use.

## Detecting AIA features in mixed results

If you have features from multiple products, check tags:
```
feature.tags[] → look for any matching "AIA \d+\.\d+\.\d+"
```
If a tag matches, the feature belongs to that AIA release.

## Standard products (ECAI, ECKN, ECAD)

These use the Release field. Fetch with `aha_get_release_features(release_id=<id>)`.
Get the release_id from `aha_list_releases` first — always pass the ID, not the name.
Release name format: YY.MM (e.g. "25.03" for March 2025).
REF

cat > config/skills/aha/references/filtering.md << 'REF'
# Feature Filtering for Release Notes

## Which features need portal articles?

Check `custom_fields[name="documents_impacted"].value`:
- Contains "release notes" (case-insensitive) → needs a portal article update
- Contains only "admin guide" or "internal only" → skip for release notes

## Field paths (JSONPath)

```
documents_impacted:  feature.custom_fields[?(@.name=="documents_impacted")].value
jira_url (primary):  feature.custom_fields[?(@.name=="jira_url")].value
jira_url (fallback): feature.integration_fields[?(@.name=="url")].value
```

## Cross-product: ECKN + ECAI

When documenting a ECKN release, scan each feature's component tags.
If a feature has an ECAI component tag → flag it in the documentation plan.
Note: "Requires ECAI review — Prasanth Sai or Carlos España should review."

## Jira URL handling

- Try `custom_fields["jira_url"]` first
- Fall back to `integration_fields["url"]`
- If both null: note it in the plan but do not block the article update
REF
```

---

### Step 3.5 — eGain skill — `SKILL.md`

```bash
cat > config/skills/egain/SKILL.md << 'SKILL'
---
name: egain
description: >
  Reads articles from the eGain Knowledge portal (read-only). Use when surveying
  existing portal content, comparing articles to planned changes, or inspecting
  article HTML. Trigger on: portal articles, knowledge base content, article comparison.
  No write APIs exist — agent presents HTML content to PM for manual apply.
---

# eGain Portal Skill (Read-Only)

## How the tools work together

- `egain_get_articles_in_topic(portal_id, topic_id)` — lists articles in a topic. Use topic IDs from `pm_context.portal_context`.
- `egain_get_article_by_id(portal_id, article_id)` — gets a single article's full HTML content. Use sparingly — only for articles likely to be updated.

Topic IDs and portal IDs come from `pm_context.portal_context` (loaded from company-context.md at session start). No "list topics" call needed.

## Output: create vs update recommendations

The eGain API is read-only — no create or update endpoints exist. When producing content:
- **Clearly matches existing article** → recommend update (show article title, ID, updated HTML)
- **No existing article covers this** → recommend create (show suggested title, topic, full HTML)
- **Ambiguous** → present both options with reasoning, let PM choose

See [references/html-format.md](references/html-format.md) for portal HTML conventions.

## Gotchas

- The API is read-only — there are NO create, update, or delete endpoints. Don't look for them.
- Topic IDs are already in `pm_context.portal_context` — don't waste a tool call trying to list topics.
- `egain_get_article_by_id` returns the full HTML body — can be large. Only call for articles you actually need to compare.
- Portal accepts HTML only: `<h2>`, `<h3>`, `<p>`, `<ul>/<li>`, `<img>`. No Markdown.
- Image URLs must be portal URLs — never use Aha CDN URLs (they require Aha auth).
- On-behalf-of-customer auth is handled by the Lambda — you never see credentials.

See references/api.md for field conventions.
SKILL
```

---

### Step 3.6 — eGain skill — `tools.py`

```python
"""
config/skills/egain/tools.py

eGain tool functions — imported directly by agent nodes.
Read-only tools for portal article inspection.
"""
from __future__ import annotations

from typing import Any
from pydantic_ai import RunContext
from tools.deps import AgentDeps

EGAIN_API_CONFIG = {
    "name": "egain",
    "base_url": "https://apidev.egain.com/apis/v4/knowledge/portalmgr/api-bundled",
    "auth": {
        "type": "basic_onbehalf",
        "credentials_secret": "pmm-agent/egain-credentials",
        "client_app_field": "client_app",
        "client_secret_field": "client_secret",
    },
    "headers": {
        "Content-Type": "application/json",
        "Accept": "application/json",
    },
}


async def egain_get_articles_in_topic(ctx: RunContext[AgentDeps], portalId: str, topicId: str) -> Any:
    """List all articles in a specific portal topic. Returns metadata including
    title, status, and last-updated date. Use to survey existing content
    before planning updates. Topic IDs come from pm_context.portal_context.

    Args:
        portalId: Portal ID from pm_context.portal_context, e.g. '1234'.
        topicId: Topic ID from pm_context.portal_context, e.g. 'topic_001'.
    """
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": "/article/getarticlesintopic",
        "params": {"portalId": portalId, "topicId": topicId},
        "api_config": EGAIN_API_CONFIG,
    })


async def egain_get_article_by_id(ctx: RunContext[AgentDeps], portalId: str, articleId: str) -> Any:
    """Get a single article's full content including HTML body. Use to inspect
    current article content for comparison with planned changes. Use sparingly
    to avoid token overload — only for articles that will likely be updated.

    Args:
        portalId: Portal ID from pm_context.portal_context.
        articleId: Article ID from egain_get_articles_in_topic results.
    """
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": "/article/getarticlebyid",
        "params": {"portalId": portalId, "articleId": articleId},
        "api_config": EGAIN_API_CONFIG,
    })


EGAIN_TOOLS = [
    egain_get_articles_in_topic,
    egain_get_article_by_id,
]
```

**Checkpoint 3.6:** `python -c "from config.skills.egain.tools import EGAIN_TOOLS; print(len(EGAIN_TOOLS), 'tools defined')"` prints `2 tools defined`.

---

### Step 3.7 — eGain skill — `references/api.md`

No `scripts/` directory needed for eGain — the two read-only tools are fully generic. Auth is handled by the `pmm-skill-client` Lambda based on the `EGAIN_API_CONFIG` constant in `tools.py` (`type: basic_onbehalf`).

No `scripts/egain_client.py` file is needed. The two read-only eGain tools are fully generic — the `pmm-skill-client` Lambda handles on-behalf-of-customer auth using `client_app` and `client_secret` from Secrets Manager, as declared in `tools.py` (`EGAIN_API_CONFIG["auth"]["type"]: basic_onbehalf`).

---

### Step 3.8 — eGain skill — `references/api.md` + company-context skill

```bash
cat > config/skills/egain/references/api.md << 'REF'
# eGain Knowledge API v4 Reference (Read-Only)

## Base URL
https://apidev.egain.com/apis/v4/knowledge/portalmgr/api-bundled

## Authentication
On-behalf-of-customer auth using client_app and client_secret from Secrets Manager.
The pmm-skill-client Lambda handles auth automatically.

## Available endpoints (read-only)

### GET /article/getarticlesintopic
Returns all articles in a specific topic.
Query params: portalId (required), topicId (required)
Returns: list of articles with id, title, status, summary, updated_at

### GET /article/getarticlebyid
Returns a single article with full HTML content.
Query params: portalId (required), articleId (required)
Returns: article with id, title, status, content_html, topic_id, updated_at

## No write endpoints
There are no create or update APIs. The agent presents HTML content to the PM
in the chat for manual application in the eGain portal.

## Content format
Portal articles use HTML. Common elements: <h2> <h3> <p> <ul> <li> <img>
Images must be re-uploaded to portal — never use Aha CDN URLs.

## Article ID format
Numeric string, e.g. "10234"

## Portal and topic IDs
Portal IDs and topic IDs are stored in company-context.md under the
"Portal Context" section. They are loaded into pm_context.portal_context
at session start. Do not hardcode these — always read from pm_context.
REF

# eGain progressive disclosure — additional reference file
cat > config/skills/egain/references/html-format.md << 'REF'
# eGain Portal HTML Format

## Supported HTML elements

Portal articles accept these HTML elements:
  <h2>   — major sections
  <h3>   — subsections
  <p>    — body paragraphs
  <ul>/<li> — bullet lists
  <ol>/<li> — numbered lists
  <img src="..."> — images (must be portal-hosted URLs)
  <a href="..."> — links
  <strong> — bold text
  <em> — italic text
  <code> — inline code

## Image handling

- Images must be uploaded to the eGain portal first
- NEVER use Aha CDN URLs — they require Aha authentication
- NEVER use external URLs that may break — download and re-upload
- Use descriptive alt text for accessibility

## Article structure conventions

- Start with <h2> for the main title/section
- Use <h3> for subsections within a <h2>
- Keep paragraphs short — PMs read these on screen
- Use bullet lists for feature descriptions
- Include version/release info in the first paragraph
REF

# Company-context skill
cat > config/skills/company-context/SKILL.md << 'SKILL'
---
name: company-context
description: >
  PM identity, product ownership, Aha product mappings, eGain portal context,
  and release cadence rules. Use when determining which products a PM owns,
  how to fetch releases for a product (AIA tags vs standard), or which portal
  topics to survey. Trigger on: PM identity, product routing, release type decisions.
---

# Company Context Skill

## What pm_context provides

All fields are parsed from `company-context.md` (S3) at session start and injected into `pm_context`:

- `pm_context.name` — PM display name (from frontend dropdown)
- `pm_context.owned_products` — product codes: `["AIA", "ECAI"]`
- `pm_context.aha_mappings` — per-product: `{aha_product_key, release_field_type, aia_version_prefix}`
- `pm_context.portal_context` — per-product: `{portal_id, portal_name, topics: [{name, id}]}`
- `pm_context.release_cadence_rules` — text summary of release rules
- `pm_context.upcoming_releases` — filtered to this PM's products only

## How to determine release fetch strategy

Check `pm_context.aha_mappings[product].release_field_type`:
- `"aia_version_tag"` → AIA: use `aha_get_release_features(product_key, tag)`
- `"standard_release"` → ECAI/ECKN/ECAD: use `aha_get_release_features(release_id)`

## Cross-product: ECKN + ECAI

ECKN features may have ECAI component dependencies.
Flag in plan: "Requires ECAI review — Prasanth Sai or Carlos España should review."

## Gotchas

- `pm_context` is loaded ONCE at session start — do not try to re-read company-context.md directly
- `portal_context` is filtered to the PM's owned products only — you won't see portals for products they don't own
- PM names come from the frontend dropdown, emails come from company-context.md — they're matched by name
- `upcoming_releases` is also filtered — a PM who owns AIA won't see ECAD releases

See [references/parsing.md](references/parsing.md) for the Markdown table format spec.
SKILL

cat > config/skills/company-context/references/parsing.md << 'REF'
# Company Context Parsing Reference

## Markdown table format in company-context.md

The PM ownership table uses pipe-delimited Markdown:
  | PM Name | Email | Owned Products | Role |

The Aha mappings table:
  | Product Name | Aha Product Code | Aha URL | Release Type | Notes |

AIA rows have Release Type = "Version tag (AIA x.x.x)"
All others have Release Type = "Standard (YY.MM)"

## PMContext struct fields populated during parsing

  pm_id                — derived from email (before @)
  name                 — "First Last" from PM Name column
  owned_products       — split on ", " from Owned Products column
  aha_mappings         — dict keyed by product code
    .aha_product_key   — e.g. "AIA", "ECAI"
    .release_field_type — "aia_version_tag" or "standard_release"
    .aia_version_prefix — "AIA" for AIA product, None for others
  portal_context       — per-product dict: {portal_id, portal_name, topics: [{name, id}]}
  release_cadence_rules — text block from "Release Cadence Rules" section
  upcoming_releases     — filtered to PM's owned products only
REF
```

**Checkpoint 3.8:** `ls config/skills/` shows three folders: `aha/`, `egain/`, `company-context/`. Each has a `SKILL.md`.

---

## Section 4 — Core Service Code

Now write the Python service layer. Build in this order — each file depends only on files already written above it.

### Step 4.1 — `company-context.md`

```bash
cat > context/company-context.md << 'CTX'
# eGain PMM Agent — Company Context

## PM to Product Ownership

| PM Name | Email | Owned Products | Role |
|---|---|---|---|
| Varsha Thalange | varsha.thalange@egain.com | AIA, ECAI, ECKN, ECAD | PM Manager |
| Aiushe Mishra | aiushe.mishra@egain.com | AIA | PM — AI Agent |
| Prasanth Sai | prasanth.sai@egain.com | AIA, ECAI | PM — AI Agent + AI Services |
| Carlos España | carlos.espana@egain.com | ECAI | PM — AI Services |
| Ankur Mehta | ankur.mehta@egain.com | ECKN | PM — Knowledge |
| Peter Huang | peter.huang@egain.com | ECKN | PM — Knowledge |
| Kevin Dohina | kevin.dohina@egain.com | ECAD | PM — Advisor Desktop |

> Note: ECKN features may have ECAI dependencies. Flag these for Prasanth Sai / Carlos España review.

---

## Aha Product to Component Mappings

| Product Name | Aha Product Code | Aha URL | Release Type | Notes |
|---|---|---|---|---|
| AI Agent | AIA | egain.aha.io/products/AIA | Version tag (AIA x.x.x) | Does NOT use Release field |
| AI Services | ECAI | egain.aha.io/products/ECAI | Standard (YY.MM) | |
| Knowledge | ECKN | egain.aha.io/products/ECKN | Standard (YY.MM) | May include cross-listed ECAI features |
| Advisor Desktop | ECAD | egain.aha.io/products/ECAD | Standard (YY.MM) | |

---

## Release Cadence Rules

### Standard Products (ECAI, ECKN, ECAD)
- Release tracked via Aha Release field on each feature
- Release name format: YY.MM (e.g. 25.03 for March 2025)

### AIA (AI Agent)
- Does NOT use the standard Aha Release field
- Tracked via attribute tags: AIA 1.0.0, AIA 1.2.0, AIA 2.0.0
- All AIA features: egain.aha.io/products/AIA/feature_cards

### Cross-product: ECKN + ECAI
- ECKN features may depend on ECAI components
- When found: flag and note Prasanth Sai / Carlos España should review

---

## Documents Impacted — Release Notes Logic
- Features tagged "release notes" under Documents Impacted → require portal update
- Each such feature will have a Jira URL in the feature record

---

## Upcoming Releases

| Release / Version | Product(s) | Target Date | Status |
|---|---|---|---|
| 25.03 | ECAI, ECKN, ECAD | March 2025 | In Progress |
| AIA 1.2.0 | AIA | March 2025 | In Progress |
| 25.06 | ECAI, ECKN, ECAD | June 2025 | Planning |
| AIA 2.0.0 | AIA | Q2 2025 | Planning |

---

## eGain Portal Context

### AIA Portal
- Portal ID: 1001
- Portal Name: eGain AI Agent Knowledge Portal

| Topic Name | Topic ID |
|---|---|
| AIA Release Notes | topic_001 |
| AIA Getting Started | topic_002 |
| AIA Configuration | topic_003 |

### ECAI Portal
- Portal ID: 1002
- Portal Name: eGain AI Services Knowledge Portal

| Topic Name | Topic ID |
|---|---|
| ECAI Release Notes | topic_010 |
| ECAI Admin Guide | topic_011 |
| ECAI API Reference | topic_012 |

### ECKN Portal
- Portal ID: 1003
- Portal Name: eGain Knowledge Product Portal

| Topic Name | Topic ID |
|---|---|
| ECKN Release Notes | topic_020 |
| ECKN Admin Guide | topic_021 |
| ECKN API Reference | topic_022 |

### ECAD Portal
- Portal ID: 1004
- Portal Name: eGain Advisor Desktop Knowledge Portal

| Topic Name | Topic ID |
|---|---|
| ECAD Release Notes | topic_030 |
| ECAD Admin Guide | topic_031 |
CTX
```

**Checkpoint 4.1:** `wc -l context/company-context.md` — file exists with content.

---

### Step 4.2 — Pydantic models

Create `services/orchestration/session/models.py`:

```python
"""
services/orchestration/session/models.py
All Pydantic models for session state and domain objects.
PMAgentState is the only model serialised to Redis — it contains no credentials.
AgentDeps is runtime-only and reconstructed per turn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from pydantic import BaseModel


class AhaMapping(BaseModel):
    product:              str
    aha_product_key:      str
    release_field_type:   str   # "aia_version_tag" | "standard_release"
    aia_version_prefix:   str | None = None  # "AIA" for AIA product, None otherwise
    shipped_tag:          str | None = None


class PMContext(BaseModel):
    pm_id:                  str
    name:                   str
    owned_products:         list[str]
    aha_mappings:           dict[str, AhaMapping]
    portal_context:         dict[str, dict]       # product → {portal_id, portal_name, topics: [{name, id}]}
    release_cadence_rules:  str
    upcoming_releases:      list[dict[str, Any]]


class ArticlePlan(BaseModel):
    title:           str
    article_id:      str | None = None   # None for creates
    folder_id:       str | None = None   # None for updates (already placed)
    folder_name:     str | None = None
    planned_changes: str
    refined_content: str | None = None
    jira_url:        str | None = None
    confirmed:       bool = False

    def is_update(self) -> bool:
        return self.article_id is not None

    def is_create(self) -> bool:
        return self.article_id is None


class IteratorState(BaseModel):
    articles:           list[ArticlePlan] = []
    current_index:      int = 0
    confirmed_articles: list[ArticlePlan] = []

    def is_done(self) -> bool:
        return self.current_index >= len(self.articles)

    def current_article(self) -> ArticlePlan:
        if self.is_done():
            raise IndexError("Iterator is done — no current article")
        return self.articles[self.current_index]


class DocumentPlan(BaseModel):
    articles_to_update: list[ArticlePlan] = []
    articles_to_create: list[ArticlePlan] = []
    rationale:          str = ""


class ToolCallRecord(BaseModel):
    """Recorded per tool call — full response is never stored."""
    tool_name:  str
    params:     dict
    timestamp:  str                          # ISO 8601
    result:     str = "tool response received"

class NodeTransition(BaseModel):
    node:       str
    timestamp:  str                          # ISO 8601


class PMAgentState(BaseModel):
    """
    The only model serialised to Redis. Contains NO credentials, NO raw context text.
    AgentDeps is reconstructed each turn from this state.
    """
    session_id:     str
    pm_name:        str                      # from frontend dropdown
    pm_context:     PMContext | None = None
    release_id:     str | None = None
    release_label:  str | None = None
    aha_specs:      list[dict] | None = None
    portal_articles:list[dict] | None = None
    plan:           DocumentPlan | None = None
    plan_feedback:  str | None = None
    plan_feedback_history: list[str] = []
    mode:           str = "unknown"      # "release" | "adhoc" | "unknown"
    mode_order:     list[str] = []       # ["updates","creates"] or ["creates","updates"]
    update_iterator: IteratorState = IteratorState()
    create_iterator: IteratorState = IteratorState()
    pm_input:       str | None = None
    adhoc_intent:   str | None = None    # "update" | "create"
    adhoc_query:    str | None = None
    current_node:   str = "EntryNode"
    last_message:   str = ""                     # last message to show PM (set by nodes)
    output_feedback: str | None = None           # feedback from OutputReviewNode
    # ── Compaction state ──────────────────────────────────────────────────────
    message_history:  list = []                   # pydantic-ai ModelMessage list (agent conversation)
    total_chars:      int = 0                     # total chars across all message parts (updated after each node)
    compaction_count: int = 0                     # number of times compaction has run this session
    compacted_summary: str | None = None          # last compaction summary (for debugging)
    # ── Audit ─────────────────────────────────────────────────────────────────
    tool_calls:     list[ToolCallRecord] = []    # accumulated during session
    node_transitions: list[NodeTransition] = []  # accumulated during session
    start_time:     str | None = None            # ISO 8601


class SessionRecord(BaseModel):
    """Written to DynamoDB (pmm-agent-sessions) once at session end. Never updated."""
    session_id:        str                   # partition key
    pm_name:           str
    pm_email:          str
    mode:              str
    release_label:     str | None = None
    start_time:        str
    end_time:          str
    status:            str                   # "completed" | "restarted"
    tool_calls:        list[ToolCallRecord] = []
    node_transitions:  list[NodeTransition] = []
```

**Checkpoint 4.2:** `python -c "from services.orchestration.session.models import PMAgentState; s=PMAgentState(session_id='test'); print(s.model_dump_json()[:80])"` prints JSON without error.

---

### Step 4.3 — Context loaders

Create `services/orchestration/context_loader/s3_loader.py`:

```python
"""
services/orchestration/context_loader/s3_loader.py
Loads company-context.md from S3 and parses it into a typed PMContext struct.
The raw Markdown is consumed here — never injected into prompts.
Process-level TTL cache: all concurrent sessions share one parse.
"""
from __future__ import annotations

import os
import re
import time
from functools import lru_cache
from typing import Any

import boto3

from session.models import AhaMapping, PMContext

_cache: dict[str, tuple[float, PMContext]] = {}
_CACHE_TTL = 300  # 5 minutes


def load_company_context(pm_email: str) -> PMContext:
    """Load and parse company-context.md; return PMContext for this PM."""
    raw = _get_raw_md()
    all_pms = _parse_all_pm_contexts(raw)
    if pm_email not in all_pms:
        raise ValueError(f"PM email '{pm_email}' not found in company-context.md")
    return all_pms[pm_email]


def invalidate_cache() -> None:
    """Called by /internal/context/invalidate when S3 is updated."""
    _cache.clear()


def _get_raw_md() -> str:
    now = time.monotonic()
    if "raw" in _cache:
        ts, val = _cache["raw"]
        if now - ts < _CACHE_TTL:
            return val
    raw = _fetch_from_s3()
    _cache["raw"] = (now, raw)
    return raw


def _fetch_from_s3() -> str:
    bucket = os.environ["CONTEXT_BUCKET"]
    s3 = boto3.client("s3")
    return s3.get_object(Bucket=bucket, Key="company-context.md")["Body"].read().decode()


def _parse_all_pm_contexts(raw_md: str) -> dict[str, PMContext]:
    """Parse the Markdown tables into a dict keyed by PM email."""
    pm_rows         = _parse_pm_ownership_table(raw_md)
    aha_mappings    = _parse_aha_mappings_table(raw_md)
    portal_context  = _parse_portal_context(raw_md)
    cadence_rules   = _parse_cadence_rules(raw_md)
    upcoming        = _parse_upcoming_releases(raw_md)

    result = {}
    for row in pm_rows:
        email    = row["email"].strip()
        products = [p.strip() for p in row["products"].split(",")]
        result[email] = PMContext(
            pm_id                  = email.split("@")[0],
            name                   = row["name"].strip(),
            owned_products         = products,
            aha_mappings           = {k: v for k, v in aha_mappings.items() if k in products},
            portal_context         = {k: v for k, v in portal_context.items() if k in products},
            release_cadence_rules  = cadence_rules,
            upcoming_releases      = [r for r in upcoming
                                      if any(p in r.get("products", "") for p in products)],
        )
    return result


def _parse_pm_ownership_table(raw_md: str) -> list[dict]:
    rows = []
    in_table = False
    for line in raw_md.splitlines():
        if "## PM to Product Ownership" in line:
            in_table = True
        if in_table and line.startswith("|") and "---|" not in line and "PM Name" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 3:
                rows.append({"name": cols[0], "email": cols[1], "products": cols[2]})
        if in_table and line.startswith("##") and "PM to Product" not in line:
            break
    return rows


def _parse_aha_mappings_table(raw_md: str) -> dict[str, AhaMapping]:
    mappings = {}
    in_table = False
    for line in raw_md.splitlines():
        if "## Aha Product to Component Mappings" in line:
            in_table = True
        if in_table and line.startswith("|") and "---|" not in line and "Product Name" not in line:
            cols = [c.strip().strip("`") for c in line.strip("|").split("|")]
            if len(cols) >= 4:
                code = cols[1]
                is_aia = "version tag" in cols[3].lower() or "AIA" in cols[3]
                mappings[code] = AhaMapping(
                    product            = cols[0],
                    aha_product_key    = code,
                    release_field_type = "aia_version_tag" if is_aia else "standard_release",
                    aia_version_prefix = "AIA" if is_aia else None,
                )
        if in_table and line.startswith("##") and "Aha Product" not in line:
            break
    return mappings


def _parse_portal_context(raw_md: str) -> dict[str, dict]:
    """Parse the 'Portal Context' section into per-product portal config.
    Returns: {"AIA": {"portal_id": "1001", "portal_name": "...", "topics": [{"name": "...", "id": "..."}]}, ...}
    """
    context = {}
    current_product = None
    current_entry: dict | None = None
    in_section = False
    for line in raw_md.splitlines():
        if "## eGain Portal Context" in line:
            in_section = True
            continue
        if in_section and line.startswith("## ") and "Portal Context" not in line:
            break
        if not in_section:
            continue
        # Detect product subsection headers like "### AIA Portal"
        if line.startswith("### ") and "Portal" in line:
            if current_product and current_entry:
                context[current_product] = current_entry
            current_product = line.replace("###", "").replace("Portal", "").strip()
            current_entry = {"portal_id": "", "portal_name": "", "topics": []}
        elif current_entry is not None:
            if line.startswith("- Portal ID:"):
                current_entry["portal_id"] = line.split(":", 1)[1].strip()
            elif line.startswith("- Portal Name:"):
                current_entry["portal_name"] = line.split(":", 1)[1].strip()
            elif line.startswith("|") and "---|" not in line and "Topic Name" not in line:
                cols = [c.strip() for c in line.strip("|").split("|")]
                if len(cols) >= 2:
                    current_entry["topics"].append({"name": cols[0], "id": cols[1]})
    if current_product and current_entry:
        context[current_product] = current_entry
    return context


def _parse_cadence_rules(raw_md: str) -> str:
    match = re.search(
        r"## Release Cadence Rules\n(.*?)(?=\n##|\Z)", raw_md, re.DOTALL
    )
    return match.group(1).strip()[:800] if match else ""


def _parse_upcoming_releases(raw_md: str) -> list[dict]:
    releases = []
    in_table = False
    for line in raw_md.splitlines():
        if "## Upcoming Releases" in line:
            in_table = True
        if in_table and line.startswith("|") and "---|" not in line and "Release" not in line:
            cols = [c.strip() for c in line.strip("|").split("|")]
            if len(cols) >= 3:
                releases.append({
                    "release": cols[0], "products": cols[1], "target": cols[2]
                })
        if in_table and line.startswith("##") and "Upcoming" not in line:
            break
    return releases
```

Create `services/orchestration/context_loader/skill_loader.py`:

```python
"""
services/orchestration/context_loader/skill_loader.py
Loads SKILL.md and references/ files from skill folders.
Skills live in the repo — loaded once at process start.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).parents[3] / "config" / "skills"


@lru_cache(maxsize=None)
def load_skill_md(skill_name: str) -> str:
    """Load SKILL.md for a named skill. Cached indefinitely — skills change with deploys."""
    path = SKILLS_DIR / skill_name / "SKILL.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_skill_reference(skill_name: str, filename: str) -> str:
    """Load a references/ file lazily — only when needed by an agent node."""
    path = SKILLS_DIR / skill_name / "references" / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""
```

Create `services/orchestration/context_loader/prompt_loader.py`:

```python
"""
services/orchestration/context_loader/prompt_loader.py
Loads prompt templates from the prompts/ folder.
Prompts are externalized so they can be iterated without code changes.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parents[3] / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    """Load a prompt template by name (without .txt extension).
    Cached indefinitely — prompts change with deploys.

    Usage:
        prompt = load_prompt("entry_node")
        formatted = prompt.format(pm_name="Prasanth", pm_products="AIA, ECAI")
    """
    path = PROMPTS_DIR / f"{name}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")
```

All agent node prompts live in `prompts/*.txt` as templates with `{variable}` placeholders. Nodes call `load_prompt("node_name").format(...)` in their `@agent.instructions` function.

**Checkpoint 4.3:** Run this test:

```bash
# Local test — uses file directly, not S3
python3 - << 'EOF'
import sys, os
os.environ["CONTEXT_BUCKET"] = "test"  # won't hit S3 in this test
sys.path.insert(0, "services/orchestration")

# Test skill loader
from context_loader.skill_loader import load_skill_md
skill = load_skill_md("aha")
assert "aha_get_release_features" in skill, "SKILL.md missing tool reference"
assert "AIA" in skill, "SKILL.md missing AIA logic"
print("✓ skill_loader OK")

# Test tools.py imports
from config.skills.aha.tools import AHA_TOOLS
from config.skills.egain.tools import EGAIN_TOOLS
assert len(AHA_TOOLS) == 4
assert len(EGAIN_TOOLS) == 2
print("✓ tools.py OK")

print("All context loader checks passed")
EOF
```

---

### Step 4.4 — Tool imports (no registry needed)

Tools are defined as plain Python functions in each skill's `tools.py` (created in Steps 3.2 and 3.6). Agent nodes import them directly — no registry layer needed.

```python
# In agent node files, tools are imported directly:
from config.skills.aha.tools import AHA_TOOLS
from config.skills.egain.tools import EGAIN_TOOLS

# Pass tools at Agent creation time:
agent = Agent(deps_type=AgentDeps, result_type=..., tools=AHA_TOOLS)
```

There is no `services/orchestration/tools/registry.py` file. Each tool function in `tools.py` already has the right signature (`ctx: RunContext` + typed params) and docstring (used as the tool description by PydanticAI). The `AHA_TOOLS` and `EGAIN_TOOLS` lists export all functions for that skill.

**Checkpoint 4.4:**

```bash
python3 - << 'EOF'
import sys
sys.path.insert(0, "services/orchestration")
from config.skills.aha.tools import AHA_TOOLS
from config.skills.egain.tools import EGAIN_TOOLS
print(f"Aha tools: {[t.__name__ for t in AHA_TOOLS]}")
print(f"eGain tools: {[t.__name__ for t in EGAIN_TOOLS]}")
EOF
```

Should print 6 tool names for each.

---

### Step 4.5 — AgentDeps

Create `services/orchestration/tools/deps.py`:

First create `services/orchestration/config.py` — this is where LLM provider config lives:

```python
"""
services/orchestration/config.py
LLM provider configuration and app settings.
Change DEFAULT_PROVIDER to switch all agent nodes — no code changes needed.
"""
from __future__ import annotations

import os

# ── LLM Provider Configuration ───────────────────────────────────────────────

PROVIDERS = {
    "gemini": {
        "name": "Gemini",
        "model": "gemini-3-flash-preview",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_env": "GEMINI_API_KEY",
        "credentials_secret": "pmm-agent/gemini-api-key",
    },
    "anthropic": {
        "name": "Anthropic",
        "model": "claude-sonnet-4-20250514",
        "base_url": "https://api.anthropic.com/v1/",
        "api_key_env": "CLAUDE_API_KEY",
        "credentials_secret": "pmm-agent/anthropic-api-key",
    },
    "openai": {
        "name": "OpenAI",
        "model": "gpt-4o",
        "base_url": "https://api.openai.com/v1/",
        "api_key_env": "OPENAI_API_KEY",
        "credentials_secret": "pmm-agent/openai-api-key",
    },
}

DEFAULT_PROVIDER = "gemini"

DEFAULT_MODEL_SETTINGS = {
    "extra_body": {"reasoning_effort": "low"},
}

# ── Context Window & Compaction ──────────────────────────────────────────────

# Context window budget: 480,000 chars ≈ 120,000 tokens (4 chars/token avg)
# Gemini Flash has 1M token context, but we cap at 120k to leave room for
# output and to keep costs/latency manageable.
CONTEXT_WINDOW_CHARS = 480_000

# Compaction triggers at 90% of context window (432,000 chars ≈ 108k tokens)
COMPACTION_TRIGGER_RATIO = 0.90
COMPACTION_TRIGGER_CHARS = int(CONTEXT_WINDOW_CHARS * COMPACTION_TRIGGER_RATIO)

# Max tokens for the compaction summary: up to 12,000 tokens (48,000 chars)
# The summary should be as concise as possible — 12k is the ceiling, not a target.
# After compaction: message_history = [summary] + [last turn]
# This occupies ~10% of context (48k chars) + last turn, leaving ~90% free.
COMPACTION_MAX_TOKENS = 12_000
COMPACTION_MAX_CHARS = COMPACTION_MAX_TOKENS * 4  # 48,000 chars ≈ 10% of context

# Number of recent conversation turns to protect from compaction.
# Only the last turn is kept verbatim — everything else is summarized.
PROTECTED_TAIL_TURNS = 1

# Max chars for a single tool response before it's capped
# Prevents one large API response from blowing the context window
MAX_TOOL_RESPONSE_CHARS = 60_000

# Prompts are loaded via context_loader/prompt_loader.py from the prompts/ folder.
# No path config needed — load_prompt("COMPACTION_PROMPT") finds prompts/COMPACTION_PROMPT.txt

# ── App Settings ─────────────────────────────────────────────────────────────

APP_ENV = os.getenv("APP_ENV", "local")
LOG_LEVEL = os.getenv("LOG_LEVEL", "debug")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CONTEXT_BUCKET = os.getenv("CONTEXT_BUCKET", "egain-pmm-agent-context-dev")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
FRONTEND_ORIGIN_DEV = os.getenv("FRONTEND_ORIGIN_DEV", "http://localhost:3000")
FRONTEND_ORIGIN_PROD = os.getenv("FRONTEND_ORIGIN_PROD", "https://pmm-agent.egain.com")
```

Now create `services/orchestration/tools/deps.py`:

```python
"""
services/orchestration/tools/deps.py
AgentDeps: runtime dependency container for PydanticAI agents.
Never serialised to Redis. Reconstructed each turn from PMAgentState.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache

import boto3
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIModel

from config import PROVIDERS, DEFAULT_PROVIDER, DEFAULT_MODEL_SETTINGS
from session.models import PMContext


class LambdaClient:
    """Thin wrapper around boto3 Lambda client for invoking skill Lambdas."""
    def __init__(self):
        self._client = boto3.client("lambda", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))

    async def invoke_skill_lambda(self, lambda_name: str, payload: dict) -> dict:
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
    Injected into every agent node via RunContext[AgentDeps].
    - lambda_client:  shared boto3 Lambda invoker — stateless, no API credentials
    - llm_model:      PydanticAI OpenAIModel configured from PROVIDERS
    - model_settings: {"extra_body": {"reasoning_effort": "low"}}
    - session_id:     used for session tracking and DynamoDB history
    - pm_context:     parsed PMContext struct, not raw text
    - aha_skill:      SKILL.md content for Aha tools
    - egain_skill:    SKILL.md content for eGain tools
    """
    lambda_client:  LambdaClient
    llm_model:      OpenAIModel
    model_settings: dict
    pm_context:     PMContext
    session_id:     str
    release_label:  str | None
    aha_skill:      str
    egain_skill:    str


# ── Process-level singletons ──────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_lambda_client() -> LambdaClient:
    return LambdaClient()


@lru_cache(maxsize=1)
def _get_llm_model() -> OpenAIModel:
    """Build PydanticAI OpenAIModel from the configured provider."""
    provider = PROVIDERS[DEFAULT_PROVIDER]
    api_key = _resolve_llm_api_key(provider)
    client = AsyncOpenAI(base_url=provider["base_url"], api_key=api_key)
    return OpenAIModel(provider["model"], openai_client=client)


def _resolve_llm_api_key(provider: dict) -> str:
    """Env var first (local dev), then Secrets Manager (prod)."""
    override = os.getenv(provider["api_key_env"])
    if override:
        return override
    sm = boto3.client("secretsmanager", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    secret = json.loads(sm.get_secret_value(SecretId=provider["credentials_secret"])["SecretString"])
    return secret["api_key"]


@lru_cache(maxsize=None)
def _get_skill_md(skill_name: str) -> str:
    from context_loader.skill_loader import load_skill_md
    return load_skill_md(skill_name)


# ── Per-session factory ───────────────────────────────────────────────────────

def build_deps(
    pm_context:    PMContext,
    session_id:    str,
    release_label: str | None = None,
) -> AgentDeps:
    """Build AgentDeps for one session turn."""
    return AgentDeps(
        lambda_client=_get_lambda_client(),
        llm_model=_get_llm_model(),
        model_settings=DEFAULT_MODEL_SETTINGS,
        pm_context=pm_context,
        session_id=session_id,
        release_label=release_label,
        aha_skill=_get_skill_md("aha"),
        egain_skill=_get_skill_md("egain"),
    )
```

**Checkpoint 4.5:**

```bash
python3 - << 'EOF'
import sys, os
sys.path.insert(0, "services/orchestration")
from dotenv import load_dotenv
load_dotenv(".env.local")
from tools.deps import _get_llm_model, _get_skill_md
from config import DEFAULT_PROVIDER, PROVIDERS
model = _get_llm_model()
print(f"✓ LLM model ready: {PROVIDERS[DEFAULT_PROVIDER]['model']} via {PROVIDERS[DEFAULT_PROVIDER]['name']}")
skill = _get_skill_md("aha")
print(f"✓ Aha skill loaded: {len(skill)} chars")
skill2 = _get_skill_md("egain")
print(f"✓ eGain skill loaded: {len(skill2)} chars")
EOF
```

---

### Step 4.6 — Redis session manager

Create `services/orchestration/session/redis_client.py`:

```python
"""
services/orchestration/session/redis_client.py
"""
from __future__ import annotations

import os
from functools import lru_cache

import redis.asyncio as redis_async

from session.models import PMAgentState

_redis_client = None


async def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_async.from_url(
            os.environ["REDIS_URL"], decode_responses=True
        )
    return _redis_client


class SessionManager:
    TTL = 86400  # 24 hours

    def __init__(self):
        self._redis = None

    async def _get_client(self):
        if not self._redis:
            self._redis = await get_redis()
        return self._redis

    async def get(self, session_id: str) -> PMAgentState | None:
        r   = await self._get_client()
        raw = await r.get(f"session:{session_id}")
        return PMAgentState.model_validate_json(raw) if raw else None

    async def save(self, session_id: str, state: PMAgentState) -> None:
        r = await self._get_client()
        await r.setex(f"session:{session_id}", self.TTL, state.model_dump_json())

    async def delete(self, session_id: str) -> None:
        r = await self._get_client()
        await r.delete(f"session:{session_id}")
```

**Checkpoint 4.6:** With Redis running (`docker compose up redis -d`):

```bash
python3 - << 'EOF'
import asyncio, sys, os
sys.path.insert(0, "services/orchestration")
from dotenv import load_dotenv
load_dotenv(".env.local")
os.environ["REDIS_URL"] = "redis://localhost:6379"

from session.redis_client import SessionManager
from session.models import PMAgentState

async def test():
    sm = SessionManager()
    state = PMAgentState(session_id="test-001", mode="release")
    await sm.save("test-001", state)
    loaded = await sm.get("test-001")
    assert loaded.session_id == "test-001"
    assert loaded.mode == "release"
    await sm.delete("test-001")
    assert await sm.get("test-001") is None
    print("✓ SessionManager save/get/delete OK")

asyncio.run(test())
EOF
```

---

### Step 4.7 — Session history (DynamoDB)

Create `services/orchestration/session/session_history.py`:

```python
"""
services/orchestration/session/session_history.py
Writes SessionRecord to DynamoDB at session end. Write-once, never updated.
Tool call results are stored as "tool response received" — never full responses.
"""
from __future__ import annotations

import os
from datetime import datetime

import boto3

from session.models import PMAgentState, SessionRecord


TABLE_NAME = "pmm-agent-sessions"


async def save_session_record(state: PMAgentState, status: str) -> None:
    """Build SessionRecord from live state and write to DynamoDB."""
    record = SessionRecord(
        session_id=state.session_id,
        pm_name=state.pm_name,
        pm_email=state.pm_context.pm_id if state.pm_context else "",
        mode=state.mode,
        release_label=state.release_label,
        start_time=state.start_time or "",
        end_time=datetime.utcnow().isoformat(),
        status=status,
        tool_calls=state.tool_calls,
        node_transitions=state.node_transitions,
    )
    ddb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    table = ddb.Table(TABLE_NAME)
    table.put_item(Item=record.model_dump())
```

**Checkpoint 4.7:**

```bash
python3 - << 'EOF'
import sys
sys.path.insert(0, "services/orchestration")
from session.models import SessionRecord, ToolCallRecord, NodeTransition
r = SessionRecord(
    session_id="test-001", pm_name="Prasanth Sai", pm_email="prasanth.sai@egain.com",
    mode="release", start_time="2026-03-18T10:00:00", end_time="2026-03-18T11:00:00",
    status="completed",
    tool_calls=[ToolCallRecord(tool_name="aha_get_release_features", params={"product_key":"AIA"}, timestamp="2026-03-18T10:05:00")],
    node_transitions=[NodeTransition(node="EntryNode", timestamp="2026-03-18T10:00:00")],
)
print(f"✓ SessionRecord: {r.session_id}, {len(r.tool_calls)} tool calls, status={r.status}")
EOF
```

---

### Step 4.8 — Compaction module

Create `services/orchestration/compaction.py`:

```python
"""
services/orchestration/compaction.py
Context window management — compacts message history when it approaches the limit.

Compaction runs BETWEEN conversation turns (not mid-turn). After the AI agent
turn completes and the user sends their next reply, the FastAPI layer calls
maybe_compact() BEFORE the next graph step begins.

Context may temporarily exceed the trigger threshold during a turn — that's
acceptable. The goal is to compact before the *next* turn starts.
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

from config import (
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
    The timestamp helps downstream agents judge data freshness and
    survives compaction (it's part of the protected tail).
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

    Called between turns — after the previous turn completes and before
    the next graph step begins.

    After compaction, message_history is permanently replaced with:
      [summary_message] + [last_turn_messages]

    The summary occupies up to ~10% of context (48k chars / 12k tokens).
    The last turn stays verbatim. Everything else is gone permanently.
    This leaves ~90% of context free for future turns.

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

    # 1. Split into compactable (everything before last turn) and last turn
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
    #    Everything else is gone. The summary is the only record of prior turns.
    summary_msg = ModelRequest(parts=[UserPromptPart(
        content=f"[COMPACTED CONVERSATION SUMMARY — compaction #{state.compaction_count + 1}]\n{summary}"
    )])
    chars_before = total_chars
    state.message_history = [summary_msg] + list(last_turn)  # permanent replacement
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
    """Find the index where the protected tail begins.
    Walks backward, counting user turns. Protects the last N turns.
    """
    if not messages:
        return 0
    turns_found = 0
    i = len(messages) - 1
    while i >= 0:
        msg = messages[i]
        if isinstance(msg, ModelRequest):
            has_user_prompt = any(isinstance(part, UserPromptPart) for part in msg.parts)
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


_compaction_agent = Agent(model=None, output_type=str)


async def _llm_summarize(model, user_prompt: str, max_tokens: int) -> str:
    """Call the LLM to produce a compaction summary."""
    result = await _compaction_agent.run(
        user_prompt=user_prompt,
        model=model,
        model_settings={"max_tokens": max_tokens, "temperature": 0.2},
    )
    return result.output


# _load_prompt removed — use context_loader.prompt_loader.load_prompt() instead
```

Create `prompts/COMPACTION_PROMPT.txt`:

```text
You are summarizing a PM documentation session to enable seamless continuation.
This summary will REPLACE the conversation history — the original messages will no
longer be accessible. Preserve everything needed to continue without loss of context,
without duplicate tool calls, and without repeating questions already asked.

Produce a structured continuation summary with these sections:

1. PM IDENTITY & SESSION STATE
   - PM name, products, release being documented
   - Current position in the graph — what node would execute next
   - Mode (release/adhoc) and mode order (updates first/creates first)

2. TOOL CALLS & RETRIEVED DATA
   For each tool call made, preserve:
   - Tool name and exact arguments used
   - Key results: feature names, article titles, content excerpts
   - Source references exactly as returned — do NOT paraphrase factual content
   This section prevents duplicate tool calls. Be thorough.

3. PLAN & ARTICLE STATE
   - The documentation plan (articles to update, articles to create)
   - Per-article: title, article ID, planned changes, confirmation status
   - Any PM feedback on the plan or individual articles

4. RESPONSES GIVEN
   - What messages were sent to the PM
   - Which articles have been confirmed/refined/skipped

5. OPEN ITEMS
   - Unresolved PM questions
   - Articles not yet reviewed
   - Any pending actions

Be concise but complete. When in doubt, include it — losing context costs more
than a slightly longer summary.

HARD LIMIT: Your summary MUST NOT exceed 48,000 characters (~12,000 tokens).

=== CONVERSATION TO SUMMARIZE ===
{conversation}
```

**Where compaction is called:** In the FastAPI `/sessions/{id}/respond` endpoint, BEFORE resuming the graph:

```python
# In the respond endpoint, after loading state and before Graph.iter():
from compaction import maybe_compact
await maybe_compact(state, deps.llm_model)
```

**Where `total_chars` is updated:** In each `BaseNode.run()` method, after calling an LLM agent:

```python
# Inside any BaseNode.run() that calls an LLM agent:
result = await some_agent.run(prompt, deps=ctx.deps, ...)
ctx.state.message_history = list(result.all_messages())
ctx.state.total_chars = count_message_chars(ctx.state.message_history)
```

**Where tool responses are capped:** In each tool function in `tools.py`:

```python
# In config/skills/aha/tools.py — each tool function:
from compaction import cap_tool_response

async def aha_get_release_features(ctx: RunContext[AgentDeps], ...) -> Any:
    raw = await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {...})
    return cap_tool_response("aha_get_release_features", str(raw))
```

**Checkpoint 4.8:**

```bash
python3 - << 'EOF'
import sys
sys.path.insert(0, "services/orchestration")
from config import (
    CONTEXT_WINDOW_CHARS, COMPACTION_TRIGGER_CHARS, COMPACTION_TARGET_CHARS,
    MAX_TOOL_RESPONSE_CHARS, PROTECTED_TAIL_TURNS,
)
print(f"Context window:    {CONTEXT_WINDOW_CHARS:,} chars ({CONTEXT_WINDOW_CHARS // 4:,} tokens)")
print(f"Compaction trigger: {COMPACTION_TRIGGER_CHARS:,} chars (90%)")
print(f"Compaction target:  {COMPACTION_TARGET_CHARS:,} chars (50%)")
print(f"Max tool response:  {MAX_TOOL_RESPONSE_CHARS:,} chars")
print(f"Protected tail:     {PROTECTED_TAIL_TURNS} turns")

from compaction import count_message_chars, cap_tool_response
# Test tool response capping
short = cap_tool_response("test", "hello")
assert "[Retrieved at" in short
long = cap_tool_response("test", "x" * 70_000)
assert "truncated" in long
print("✓ Compaction module OK")
EOF
```

---

## Section 5 — Graph Nodes

Build graph nodes in dependency order. Each node can be manually tested before building the next.

**Prompt externalization pattern:** All LLM agent prompts live in `prompts/*.txt` as templates with `{variable}` placeholders. Nodes load them via `load_prompt("node_name").format(...)`:

```python
# Every LLM node's @agent.instructions follows this pattern:
@some_agent.instructions
async def instructions(ctx: RunContext[AgentDeps]) -> str:
    from context_loader.prompt_loader import load_prompt
    return load_prompt("some_node").format(
        pm_name=ctx.deps.pm_context.name,
        pm_products=", ".join(ctx.deps.pm_context.owned_products),
        # ... other variables specific to this node
    )
```

Prompt files: `prompts/entry_node.txt`, `prompts/release_confirm_node.txt`, `prompts/release_context_node.txt`, `prompts/portal_context_node.txt`, `prompts/plan_gen_node.txt`, `prompts/plan_review_node.txt`, `prompts/output_node.txt`, `prompts/output_review_node.txt`, `prompts/adhoc_router_node.txt`, `prompts/suggest_node.txt`, `prompts/update_feedback_node.txt`, `prompts/refine_node.txt`, `prompts/COMPACTION_PROMPT.txt`.

### Step 5.1 — EntryNode

Create `services/orchestration/graph/nodes/entry.py`:

```python
"""EntryNode: identify PM, load context, route to release or ad-hoc flow."""
from __future__ import annotations

from dataclasses import dataclass
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from pydantic_graph import BaseNode, GraphRunContext
from tools.deps import AgentDeps
from session.models import PMAgentState


# ── LLM Agent (called inside BaseNode.run) ─────────────────────────────────

class EntryResult(BaseModel):
    message:       str
    next_node:     str   # "ContextSetupNode" | "AdHocRouterNode" | "EntryNode"
    awaiting_input: bool = False


entry_agent: Agent[AgentDeps, EntryResult] = Agent(
    deps_type=AgentDeps,
    result_type=EntryResult,
)


@entry_agent.instructions
async def entry_instructions(ctx: RunContext[AgentDeps]) -> str:
    from context_loader.prompt_loader import load_prompt
    pm = ctx.deps.pm_context
    return load_prompt("entry_node").format(
        pm_name=pm.name,
        pm_products=", ".join(pm.owned_products),
    )


# ── Graph Node ──────────────────────────────────────────────────────────────

@dataclass
class EntryNode(BaseNode[PMAgentState, AgentDeps]):
    """LLM reasoning — identify PM, greet, route to release or ad-hoc flow."""

    async def run(
        self, ctx: GraphRunContext[PMAgentState, AgentDeps]
    ) -> ContextSetupNode | AdHocRouterNode | EntryNode:
        prompt = ctx.state.pm_input or "Hello, I need to update documentation."
        ctx.state.pm_input = None  # consumed

        result = await entry_agent.run(
            prompt, deps=ctx.deps,
            model=ctx.deps.llm_model, model_settings=ctx.deps.model_settings,
        )
        ctx.state.last_message = result.output.message

        if result.output.next_node == "AdHocRouterNode":
            return AdHocRouterNode()
        if result.output.awaiting_input:
            return EntryNode()  # loop back — PM needs to clarify
        return ContextSetupNode()
```

**Key pattern:** The `Agent` is defined at module level (same as before). The `BaseNode.run()` method calls the agent, mutates `ctx.state`, and returns the next node class instance. The return type annotation (`-> ContextSetupNode | AdHocRouterNode | EntryNode`) defines valid edges — type-checked when the `Graph` is constructed.



**Checkpoint 5.1 — EntryNode:** Run the test above. It should print a greeting and `next_node: ContextSetupNode`.

---

### Step 5.2 — ContextSetupNode

Create `services/orchestration/graph/nodes/context_setup.py`:

```python
"""ContextSetupNode: Python logic — validates pm_context is loaded. No LLM call."""
from __future__ import annotations

from dataclasses import dataclass
from pydantic_graph import BaseNode, GraphRunContext
from tools.deps import AgentDeps
from session.models import PMAgentState

# NOTE: Uses Python logic now. Upgrade to LLM agent when this node needs
# reasoning (e.g., when new capabilities require context validation decisions).


@dataclass
class ContextSetupNode(BaseNode[PMAgentState, AgentDeps]):
    """Python logic — validates pm_context is loaded and has Aha mappings."""

    async def run(
        self, ctx: GraphRunContext[PMAgentState, AgentDeps]
    ) -> ReleaseConfirmNode:
        pm = ctx.state.pm_context
        if not pm or not pm.aha_mappings:
            raise ValueError(f"No Aha product mappings found for PM")
        products = ", ".join(pm.owned_products)
        ctx.state.last_message = f"Context loaded for {pm.name}. Products: {products}. Ready to proceed."
        return ReleaseConfirmNode()
```

**Python-logic nodes use the exact same `BaseNode` pattern** — they just don't call an LLM agent inside `run()`. This makes it trivial to upgrade to an LLM agent later: add an `Agent` and call it inside `run()`, without changing the graph structure or edges.

---

### Step 5.3 — ReleaseConfirmNode (HITL Gate 1)

Create `services/orchestration/graph/nodes/release_confirm.py`:

```python
"""
ReleaseConfirmNode — HITL Gate 1.
Lists active releases for the PM's products and waits for them to pick one.
For AIA products: lists version tags. For ECAI/ECKN/ECAD: lists standard releases.
"""
from __future__ import annotations
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps


class ReleaseConfirmResult(BaseModel):
    message:        str
    awaiting_input: bool = True
    next_node:      str  = "ReleaseConfirmNode"
    release_id:     str | None = None
    release_label:  str | None = None


release_confirm_agent: Agent[AgentDeps, ReleaseConfirmResult] = Agent(
    deps_type=AgentDeps,
    # model passed at agent.run() time from deps.llm_model
    result_type=ReleaseConfirmResult,
)


@release_confirm_agent.instructions
async def release_confirm_instructions(ctx: RunContext[AgentDeps]) -> str:
    from context_loader.prompt_loader import load_prompt
    pm = ctx.deps.pm_context
    return load_prompt("release_confirm_node").format(
        pm_name=pm.name,
        pm_products=", ".join(pm.owned_products),
    )


async def run_release_confirm_node(state, deps, pm_input: str | None = None) -> ReleaseConfirmResult:
    prompt = pm_input or "Please list available releases for my products."
    result = await release_confirm_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output
```

---

### Step 5.4 — ReleaseContextAgentNode (Tool-Agent Node)

Create `services/orchestration/graph/nodes/release_context_agent.py`:

```python
"""
ReleaseContextAgentNode — Tool-Agent Node.
Fetches all Aha release context: features with full details, images, Jira URLs.
Uses Aha tools. Typically 1–3 Lambda calls (single call returns all features with details).
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps
from config.skills.aha.tools import AHA_TOOLS


class FeatureSpec(BaseModel):
    id:            str
    name:          str
    description:   str
    jira_url:      str | None
    documents_impacted: str
    tags:          list[str] = []
    attachments:   list[dict] = []


class ReleaseContextResult(BaseModel):
    features:      list[FeatureSpec]
    product_key:   str
    release_label: str
    component_summary: str


release_context_agent: Agent[AgentDeps, ReleaseContextResult] = Agent(
    deps_type=AgentDeps,
    # model passed at agent.run() time from deps.llm_model
    result_type=ReleaseContextResult,
    max_result_retries=3,
    tools=AHA_TOOLS,
)


@release_context_agent.instructions
async def release_context_instructions(ctx: RunContext[AgentDeps]) -> str:
    pm       = ctx.deps.pm_context
    mappings = "\n".join(
        f"- {code}: key={m.aha_product_key}, type={m.release_field_type}"
        + (f", aia_prefix={m.aia_version_prefix}" if m.aia_version_prefix else "")
        for code, m in pm.aha_mappings.items()
    )
    return f"""You are gathering Aha release context for {pm.name}.
Current release: {ctx.deps.release_label}
PM products: {", ".join(pm.owned_products)}

Aha product mappings:
{mappings}

Cadence rule: {pm.release_cadence_rules}

--- Tool usage rules ---
{ctx.deps.aha_skill}
"""


async def run_release_context_agent_node(state, deps) -> ReleaseContextResult:
    prompt = (
        f"Gather complete Aha context for release '{state.release_label}'. "
        f"Follow the tool usage rules. Return structured data."
    )
    result = await release_context_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output
```

---

### Step 5.5 — PortalContextAgentNode (Tool-Agent Node)

Create `services/orchestration/graph/nodes/portal_context_agent.py`:

```python
"""
PortalContextAgentNode — Tool-Agent Node.
Surveys eGain portal: lists topics, browses articles, gets summaries.
Uses eGain tools.
"""
from __future__ import annotations
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps
from config.skills.egain.tools import EGAIN_TOOLS


class PortalArticle(BaseModel):
    id:          str
    title:       str
    topic_id:    str
    topic_name:  str
    status:      str
    summary:     str


class PortalContextResult(BaseModel):
    articles:     list[PortalArticle]
    topics:       list[dict]
    survey_notes: str


portal_context_agent: Agent[AgentDeps, PortalContextResult] = Agent(
    deps_type=AgentDeps,
    # model passed at agent.run() time from deps.llm_model
    result_type=PortalContextResult,
    tools=EGAIN_TOOLS,
)


@portal_context_agent.instructions
async def portal_context_instructions(ctx: RunContext[AgentDeps]) -> str:
    pm = ctx.deps.pm_context
    portal_info = ""
    for product, pctx in pm.portal_context.items():
        topics = "\n".join(f"    - {t['name']}: {t['id']}" for t in pctx["topics"])
        portal_info += f"  {product} — Portal ID: {pctx['portal_id']} ({pctx['portal_name']})\n{topics}\n"
    return f"""You are surveying the eGain portal for {pm.name}.
Release being documented: {ctx.deps.release_label}
PM products: {", ".join(pm.owned_products)}

Portal context (use these IDs in tool calls):
{portal_info}

--- Tool usage rules ---
{ctx.deps.egain_skill}
"""


async def run_portal_context_agent_node(state, deps) -> PortalContextResult:
    prompt = (
        f"Survey the eGain portal for articles relevant to {state.release_label}. "
        f"Focus on the PM's product folders and the Release Notes folder."
    )
    result = await portal_context_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output
```

---

### Step 5.6 — PlanGenNode

Create `services/orchestration/graph/nodes/plan_gen.py`:

```python
"""
PlanGenNode — pure LLM reasoning, no tools.
Matches Aha features to existing portal articles → DocumentPlan.
Re-runs if state.plan_feedback is set (PM edited the plan).
"""
from __future__ import annotations
import json
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps
from session.models import ArticlePlan, DocumentPlan


class PlanGenResult(BaseModel):
    plan:      DocumentPlan
    rationale: str


plan_gen_agent: Agent[AgentDeps, PlanGenResult] = Agent(
    deps_type=AgentDeps,
    # model passed at agent.run() time from deps.llm_model
    result_type=PlanGenResult,
)


@plan_gen_agent.instructions
async def plan_gen_instructions(ctx: RunContext[AgentDeps]) -> str:
    pm = ctx.deps.pm_context
    return f"""You are a documentation planning assistant for {pm.name}.
Release: {ctx.deps.release_label}
Products: {", ".join(pm.owned_products)}

Available portal context: {json.dumps(pm.portal_context)}

Your task:
1. For each Aha feature tagged 'release notes': decide if an existing article needs
   updating, or a new article should be created.
2. Match features to articles by title similarity and topic area.
3. For updates: identify which article (by ID) and summarise planned changes.
4. For creates: suggest a title and folder_id from the folder structure above.
5. If plan_feedback is provided in the prompt, incorporate it.

Always set jira_url on each article plan if the feature has one.
Release notes articles always go in the Release Notes folder (folder_006).
"""


async def run_plan_gen_node(state, deps) -> PlanGenResult:
    aha_summary   = json.dumps([f.model_dump() if hasattr(f, 'model_dump') else f
                                for f in (state.aha_specs or [])], indent=2)[:3000]
    portal_summary = json.dumps([a.model_dump() if hasattr(a, 'model_dump') else a
                                  for a in (state.portal_articles or [])], indent=2)[:3000]
    feedback_note = ""
    if state.plan_feedback:
        feedback_note = f"\n\nPM FEEDBACK ON PREVIOUS PLAN — incorporate this:\n{state.plan_feedback}"

    prompt = f"""Generate a documentation update plan.

Aha release features:
{aha_summary}

Current portal articles:
{portal_summary}
{feedback_note}
"""
    result = await plan_gen_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output
```

---

### Step 5.7 — PlanReviewNode (HITL Gate 2)

Create `services/orchestration/graph/nodes/plan_review.py`:

```python
"""
PlanReviewNode — HITL Gate 2.
Presents DocumentPlan to PM. On confirm → ModeSelectNode. On edit → PlanGenNode.
"""
from __future__ import annotations
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps
from session.models import DocumentPlan


class PlanReviewResult(BaseModel):
    message:        str
    awaiting_input: bool = True
    next_node:      str  = "PlanReviewNode"
    plan_feedback:  str | None = None   # set when PM wants changes


plan_review_agent: Agent[AgentDeps, PlanReviewResult] = Agent(
    deps_type=AgentDeps,
    # model passed at agent.run() time from deps.llm_model
    result_type=PlanReviewResult,
)


@plan_review_agent.instructions
async def plan_review_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""You are presenting a documentation plan for review to {ctx.deps.pm_context.name}.
Release: {ctx.deps.release_label}

Present the plan clearly: list articles to update and articles to create.
For each, show the title, what will change, and the Jira URL.

Then ask for confirmation.

When PM responds:
- "confirm" / "looks good" / "ok" / "yes" / "proceed" → next_node="ModeSelectNode", awaiting_input=False
- Anything else (feedback/edit request) → capture as plan_feedback, next_node="PlanGenNode", awaiting_input=False
"""


async def run_plan_review_node(state, deps, pm_input: str | None = None) -> PlanReviewResult:
    import json
    if pm_input is None:
        # First time — format and present the plan
        plan = state.plan
        prompt = f"Present this plan for review:\n{plan.model_dump_json(indent=2) if plan else 'No plan yet'}"
    else:
        prompt = f"PM responded: {pm_input}"
    result = await plan_review_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output
```

---

### Step 5.8 — ModeSelectNode (HITL Gate 3)

Create `services/orchestration/graph/nodes/mode_select.py`:

```python
"""ModeSelectNode — HITL Gate 3. Ask PM: updates first or new articles first?"""
from __future__ import annotations
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps


class ModeSelectResult(BaseModel):
    message:        str
    awaiting_input: bool = True
    next_node:      str  = "ModeSelectNode"
    mode_order:     list[str] = []   # ["updates","creates"] or ["creates","updates"]


mode_select_agent: Agent[AgentDeps, ModeSelectResult] = Agent(
    deps_type=AgentDeps,
    # model passed at agent.run() time from deps.llm_model
    result_type=ModeSelectResult,
)


@mode_select_agent.instructions
async def mode_select_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""Ask {ctx.deps.pm_context.name} whether to start with updating
existing articles or creating new ones.

When PM responds:
- "updates" / "update first" / "existing" → mode_order=["updates","creates"], next_node="ShowUpdatePlan", awaiting_input=False
- "creates" / "new" / "new articles" → mode_order=["creates","updates"], next_node="ShowCreatePlan", awaiting_input=False
- Unclear → re-prompt (awaiting_input=True)
"""


async def run_mode_select_node(state, deps, pm_input: str | None = None) -> ModeSelectResult:
    prompt = pm_input or "Shall we start with updating existing articles or creating new ones?"
    result = await mode_select_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output
```

---

### Step 5.9 — UpdateIterator Nodes

Create `services/orchestration/graph/nodes/update_iterator.py`:

```python
"""
Update Iterator — per-article loop for updates.
Four node functions: ShowUpdatePlan, UpdateFeedbackGate (HITL), RefineUpdate, AdvanceUpdateIndex.
"""
from __future__ import annotations
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps
from session.models import ArticlePlan, IteratorState


# ── Shared result type ────────────────────────────────────────────────────────

class UpdateIteratorResult(BaseModel):
    message:        str
    awaiting_input: bool = False
    next_node:      str  = "UpdateFeedbackGate"
    refined_content: str | None = None


# ── Agents ────────────────────────────────────────────────────────────────────

show_update_agent: Agent[AgentDeps, UpdateIteratorResult] = Agent(
    deps_type=AgentDeps, result_type=UpdateIteratorResult)  # model from deps.llm_model

feedback_agent: Agent[AgentDeps, UpdateIteratorResult] = Agent(
    deps_type=AgentDeps, result_type=UpdateIteratorResult)  # model from deps.llm_model

refine_agent: Agent[AgentDeps, UpdateIteratorResult] = Agent(
    deps_type=AgentDeps, result_type=UpdateIteratorResult)  # model from deps.llm_model


@show_update_agent.instructions
async def show_update_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""Present the current article update plan to {ctx.deps.pm_context.name}.
Show: article title, what will be changed, Jira reference.
Then ask for confirmation or feedback. Set awaiting_input=True, next_node="UpdateFeedbackGate"."""


@feedback_agent.instructions
async def feedback_gate_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""Process PM feedback for {ctx.deps.pm_context.name} on the current article update.
- "confirm" / "yes" / "ok" / "looks good" / "lgtm" → next_node="AdvanceUpdateIndex", awaiting_input=False
- Any actual feedback → next_node="RefineUpdate", awaiting_input=False, include feedback in message
"""


@refine_agent.instructions
async def refine_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""Refine the article content based on {ctx.deps.pm_context.name}'s feedback.
Produce updated content in HTML. Set next_node="ShowUpdatePlan" to show the refined version."""


# ── Node runners ──────────────────────────────────────────────────────────────

async def run_show_update_plan(state, deps) -> UpdateIteratorResult:
    article = state.update_iterator.current_article()
    prompt  = f"Present this article update plan:\nTitle: {article.title}\nChanges: {article.planned_changes}\nJira: {article.jira_url}"
    result  = await show_update_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output


async def run_update_feedback_gate(state, deps, pm_input: str) -> UpdateIteratorResult:
    result = await feedback_agent.run(pm_input, deps=deps,
                                          model=deps.llm_model, model_settings=deps.model_settings)
    # If confirmed: mark article confirmed in state
    if result.output.next_node == "AdvanceUpdateIndex":
        article = state.update_iterator.current_article()
        article.confirmed = True
        state.update_iterator.confirmed_articles.append(article)
    return result.output


async def run_refine_update(state, deps, pm_feedback: str) -> UpdateIteratorResult:
    article = state.update_iterator.current_article()
    prompt  = f"Article: {article.title}\nCurrent plan: {article.planned_changes}\nPM feedback: {pm_feedback}\nRefine and produce updated HTML content."
    result  = await refine_agent.run(prompt, deps=deps,
                                         model=deps.llm_model, model_settings=deps.model_settings)
    # Store refined content in state
    if result.output.refined_content:
        article.refined_content = result.output.refined_content
    return result.output


async def run_advance_update_index(state, deps) -> UpdateIteratorResult:
    state.update_iterator.current_index += 1
    if state.update_iterator.is_done():
        # All updates done — route to creates or output
        if "creates" in state.mode_order and state.create_iterator.articles:
            next_node = "ShowCreatePlan"
        else:
            next_node = "OutputAgentNode"
        return UpdateIteratorResult(
            message="All article updates confirmed.",
            next_node=next_node,
        )
    return UpdateIteratorResult(
        message="Moving to next article.",
        next_node="ShowUpdatePlan",
    )
```

---

### Step 5.10 — CreateIterator Nodes

Create `services/orchestration/graph/nodes/create_iterator.py`:

```python
"""
Create Iterator — per-article loop for new articles.
Mirrors UpdateIterator exactly but for creates.
"""
from __future__ import annotations
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps


class CreateIteratorResult(BaseModel):
    message:        str
    awaiting_input: bool = False
    next_node:      str  = "CreateFeedbackGate"
    draft_content:  str | None = None


show_create_agent:   Agent[AgentDeps, CreateIteratorResult] = Agent(
    deps_type=AgentDeps, result_type=CreateIteratorResult)  # model from deps.llm_model
create_feedback_agent: Agent[AgentDeps, CreateIteratorResult] = Agent(
    deps_type=AgentDeps, result_type=CreateIteratorResult)  # model from deps.llm_model
refine_create_agent:  Agent[AgentDeps, CreateIteratorResult] = Agent(
    deps_type=AgentDeps, result_type=CreateIteratorResult)  # model from deps.llm_model


@show_create_agent.instructions
async def show_create_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""Present the new article plan to {ctx.deps.pm_context.name}.
Show: proposed title, destination folder, outline of content, Jira reference.
Generate a draft in HTML. Ask for confirmation or feedback. awaiting_input=True."""


@create_feedback_agent.instructions
async def create_feedback_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""Process PM feedback on the new article draft for {ctx.deps.pm_context.name}.
- "confirm" / "yes" / "ok" / "looks good" → next_node="AdvanceCreateIndex", awaiting_input=False
- Any feedback → next_node="RefineCreate", awaiting_input=False
"""


@refine_create_agent.instructions
async def refine_create_instructions(ctx: RunContext[AgentDeps]) -> str:
    return "Refine the new article based on PM feedback. Produce updated HTML. next_node='ShowCreatePlan'."


async def run_show_create_plan(state, deps) -> CreateIteratorResult:
    article = state.create_iterator.current_article()
    prompt  = f"Generate a draft for new article:\nTitle: {article.title}\nFolder: {article.folder_id}\nPlan: {article.planned_changes}"
    result  = await show_create_agent.run(prompt, deps=deps,
                                             model=deps.llm_model, model_settings=deps.model_settings)
    if result.output.draft_content:
        article.refined_content = result.output.draft_content
    return result.output


async def run_create_feedback_gate(state, deps, pm_input: str) -> CreateIteratorResult:
    result = await create_feedback_agent.run(pm_input, deps=deps,
                                                model=deps.llm_model, model_settings=deps.model_settings)
    if result.output.next_node == "AdvanceCreateIndex":
        article = state.create_iterator.current_article()
        article.confirmed = True
        state.create_iterator.confirmed_articles.append(article)
    return result.output


async def run_refine_create(state, deps, pm_feedback: str) -> CreateIteratorResult:
    article = state.create_iterator.current_article()
    prompt  = f"Title: {article.title}\nDraft: {article.refined_content or article.planned_changes}\nFeedback: {pm_feedback}"
    result  = await refine_create_agent.run(prompt, deps=deps,
                                               model=deps.llm_model, model_settings=deps.model_settings)
    if result.output.draft_content:
        article.refined_content = result.output.draft_content
    return result.output


async def run_advance_create_index(state, deps) -> CreateIteratorResult:
    state.create_iterator.current_index += 1
    if state.create_iterator.is_done():
        return CreateIteratorResult(
            message="All new articles confirmed.", next_node="OutputAgentNode")
    return CreateIteratorResult(
        message="Moving to next article.", next_node="ShowCreatePlan")
```

---

### Step 5.11 — OutputAgentNode (Tool-Agent Node)

Create `services/orchestration/graph/nodes/output_agent.py`:

```python
"""
OutputAgentNode — LLM Reasoning Node.
Presents finalised article HTML to the PM with create/update/both recommendations.
No eGain tools — eGain integration is read-only. PM applies changes manually in portal.
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps


class OutputArticle(BaseModel):
    title:          str
    article_id:     str | None = None   # set for updates, None for creates
    recommendation: str                 # "create" | "update" | "both"
    reasoning:      str                 # why this recommendation
    html_content:   str                 # full article HTML for PM to apply
    target_article: str | None = None   # existing article title (for update recommendation)


class OutputResult(BaseModel):
    articles:  list[OutputArticle]
    count:     int
    summary:   str   # human-readable summary for the PM


output_agent: Agent[AgentDeps, OutputResult] = Agent(
    deps_type=AgentDeps,
    # model passed at agent.run() time from deps.llm_model
    result_type=OutputResult,
    # No eGain tools registered — this is pure LLM reasoning (no write APIs exist)
)


@output_agent.instructions
async def output_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""You are presenting final documentation content to the PM.
Release: {ctx.deps.release_label}

The eGain portal has NO write APIs. You cannot create or update articles directly.
Instead, present the content for the PM to manually apply in the portal.

For each confirmed article, you must:
1. Generate the full HTML content (using <h2>, <h3>, <p>, <ul>/<li>, <img> elements).
2. Recommend one of three actions:
   - "create" — when no existing article covers this content.
     Include: suggested title, suggested topic/folder, full HTML.
   - "update" — when an existing article clearly matches.
     Include: existing article title, article ID, full updated HTML.
   - "both" — when it's ambiguous. Present both options with reasoning
     and let the PM choose.

Decision rules:
- If an existing article title closely matches the planned content → recommend "update".
- If no existing article covers the topic → recommend "create".
- If an existing article partially covers it but a new dedicated article would be cleaner
  → present "both" options with reasoning.

Return all articles with their HTML content and recommendations.
"""


async def run_output_agent_node(state, deps) -> OutputResult:
    updates = state.update_iterator.confirmed_articles
    creates = state.create_iterator.confirmed_articles

    import json
    updates_json = json.dumps(
        [a.model_dump() for a in updates], indent=2)[:2000]
    creates_json = json.dumps(
        [a.model_dump() for a in creates], indent=2)[:2000]

    prompt = f"""Present the following confirmed articles to the PM with HTML content
and create/update recommendations:

UPDATES ({len(updates)} articles):
{updates_json}

NEW ARTICLES ({len(creates)} articles):
{creates_json}

Generate full HTML content for each article and recommend whether to create a new
article, update an existing one, or present both options.
"""
    result = await output_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output
```

---

### Step 5.12 — AdHoc Flow Nodes

Create `services/orchestration/graph/nodes/adhoc_router.py`:

```python
"""AdHocRouterNode — entry point for ad-hoc (non-release) article changes."""
from __future__ import annotations
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps


class AdHocResult(BaseModel):
    message:        str
    awaiting_input: bool = True
    next_node:      str  = "AdHocRouterNode"
    adhoc_intent:   str | None = None   # "update" | "create"


adhoc_agent: Agent[AgentDeps, AdHocResult] = Agent(
    deps_type=AgentDeps, result_type=AdHocResult)  # model from deps.llm_model


@adhoc_agent.instructions
async def adhoc_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""Guide {ctx.deps.pm_context.name} to the right flow for an ad-hoc change.
Ask: do they want to update an existing article or create a new one?
Do they know which article, or should the agent suggest?

When intent is clear:
- Update + knows article → adhoc_intent="update", next_node="AskArticleNode", awaiting_input=False
- Create              → adhoc_intent="create", next_node="AskArticleNode", awaiting_input=False
- Needs suggestion    → next_node="SuggestNode", awaiting_input=False
"""


async def run_adhoc_router_node(state, deps, pm_input: str | None = None) -> AdHocResult:
    prompt = pm_input or "I need to make a specific article change."
    result = await adhoc_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output
```

Create `services/orchestration/graph/nodes/suggest.py`:

```python
"""SuggestNode — searches portal and suggests best matching article to PM."""
from __future__ import annotations
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps
from config.skills.egain.tools import EGAIN_TOOLS


class SuggestResult(BaseModel):
    message:            str
    awaiting_input:     bool = True
    next_node:          str  = "SuggestNode"
    suggested_article_id: str | None = None


suggest_agent: Agent[AgentDeps, SuggestResult] = Agent(
    deps_type=AgentDeps, result_type=SuggestResult,
    tools=EGAIN_TOOLS)  # model from deps.llm_model


@suggest_agent.instructions
async def suggest_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""Search the eGain portal to find the best article to update for {ctx.deps.pm_context.name}.
Use egain_get_articles_in_topic to find candidates.
Present the best match with title, topic, and summary.
Ask PM to confirm.

PM confirms → suggested_article_id=<id>, next_node="ShowUpdatePlan" or "ShowCreatePlan", awaiting_input=False
PM rejects  → search again with different terms, awaiting_input=True

--- Tool usage rules ---
{ctx.deps.egain_skill}
"""


async def run_suggest_node(state, deps, pm_input: str | None = None) -> SuggestResult:
    prompt = pm_input or f"Find a relevant article to update for the PM's products: {', '.join(state.pm_context.owned_products)}"
    result = await suggest_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output
```

Create `services/orchestration/graph/nodes/ask_article.py`:

```python
"""AskArticleNode — collect article ID (update) or folder (create) from PM."""
from __future__ import annotations
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from tools.deps import AgentDeps
from config.skills.egain.tools import EGAIN_TOOLS
from session.models import ArticlePlan, IteratorState


class AskArticleResult(BaseModel):
    message:        str
    awaiting_input: bool = True
    next_node:      str  = "AskArticleNode"


ask_agent: Agent[AgentDeps, AskArticleResult] = Agent(
    deps_type=AgentDeps, result_type=AskArticleResult,
    tools=EGAIN_TOOLS)  # model from deps.llm_model


@ask_agent.instructions
async def ask_article_instructions(ctx: RunContext[AgentDeps]) -> str:
    return f"""Help {ctx.deps.pm_context.name} specify the article to work on.
If updating: ask for the article ID or title. Use egain_get_article_by_id to confirm it exists.
If creating: ask for the title and call egain_get_articles_in_topic to show available folders.
  
When PM has confirmed the article:
- Update → populate update_iterator with one ArticlePlan, next_node="ShowUpdatePlan", awaiting_input=False
- Create → populate create_iterator with one ArticlePlan, next_node="ShowCreatePlan", awaiting_input=False
"""


async def run_ask_article_node(state, deps, pm_input: str | None = None) -> AskArticleResult:
    intent = state.adhoc_intent or "update"
    prompt = pm_input or f"PM wants to {intent} an article. Ask them which one."
    result = await ask_agent.run(prompt, deps=deps,
                                    model=deps.llm_model, model_settings=deps.model_settings)
    return result.output
```

---

### Step 5.13 — Graph Assembly

Create `services/orchestration/graph/graph.py`:

```python
"""
services/orchestration/graph/graph.py
PydanticAI Graph construction — no dispatch() function.
All routing is handled by BaseNode return types, validated at construction.
"""
from __future__ import annotations

from pydantic_graph import Graph, End
from session.models import PMAgentState
from tools.deps import AgentDeps

# Import all node classes
from graph.nodes.entry import EntryNode
from graph.nodes.context_setup import ContextSetupNode
from graph.nodes.release_confirm import ReleaseConfirmNode
from graph.nodes.release_context_agent import ReleaseContextAgentNode
from graph.nodes.portal_context_agent import PortalContextAgentNode
from graph.nodes.plan_gen import PlanGenNode
from graph.nodes.plan_review import PlanReviewNode
from graph.nodes.mode_select import ModeSelectNode
from graph.nodes.update_iterator import (
    ShowUpdatePlanNode, UpdateFeedbackNode, RefineUpdateNode, AdvanceUpdateNode,
)
from graph.nodes.create_iterator import (
    ShowCreatePlanNode, CreateFeedbackNode, RefineCreateNode, AdvanceCreateNode,
)
from graph.nodes.output_agent import OutputAgentNode
from graph.nodes.output_review import OutputReviewNode
from graph.nodes.done import DoneNode
from graph.nodes.adhoc_router import AdHocRouterNode
from graph.nodes.suggest import SuggestNode
from graph.nodes.ask_article import AskArticleNode

# ── Graph constructed once at module level ───────────────────────────────────
# All edges are validated via BaseNode return type annotations.
# If a node returns a class not in this list, construction fails immediately.

pmm_graph = Graph(
    nodes=[
        EntryNode, ContextSetupNode, ReleaseConfirmNode,
        ReleaseContextAgentNode, PortalContextAgentNode,
        PlanGenNode, PlanReviewNode, ModeSelectNode,
        ShowUpdatePlanNode, UpdateFeedbackNode, RefineUpdateNode, AdvanceUpdateNode,
        ShowCreatePlanNode, CreateFeedbackNode, RefineCreateNode, AdvanceCreateNode,
        OutputAgentNode, OutputReviewNode, DoneNode,
        AdHocRouterNode, SuggestNode, AskArticleNode,
    ],
    state_type=PMAgentState,
    deps_type=AgentDeps,
)


# ── HITL helpers ─────────────────────────────────────────────────────────────

HITL_NODES = {
    "EntryNode",           # may loop back for clarification
    "ReleaseConfirmNode",  # HITL #1
    "PlanReviewNode",      # HITL #2
    "ModeSelectNode",      # HITL #3
    "UpdateFeedbackNode",  # HITL #4
    "CreateFeedbackNode",  # HITL #5
    "OutputReviewNode",    # HITL #6
    "AdHocRouterNode",     # ad-hoc HITL
}


def is_hitl_node(node) -> bool:
    """Check if the next node needs PM input before it can run."""
    return type(node).__name__ in HITL_NODES


def get_node_class(node_name: str):
    """Resolve a node class from its string name (for session resume)."""
    node_map = {cls.__name__: cls for cls in pmm_graph.nodes}
    cls = node_map.get(node_name)
    if not cls:
        raise ValueError(f"Unknown node: {node_name}")
    return cls
```

**Checkpoint 5.13:**

```bash
python3 - << 'EOF'
import sys
sys.path.insert(0, "services/orchestration")
from graph.graph import pmm_graph, is_hitl_node, get_node_class
print(f"✓ Graph constructed with {len(pmm_graph.nodes)} node classes")
print(f"✓ Mermaid diagram:\n{pmm_graph.mermaid_code(start_node=get_node_class('EntryNode'))[:500]}")

# Verify all node classes are present
from graph.nodes.entry import EntryNode
from graph.nodes.output_review import OutputReviewNode
from graph.nodes.done import DoneNode
assert is_hitl_node(OutputReviewNode())
assert not is_hitl_node(DoneNode())
print("✓ HITL detection works")
EOF
```

---


## Section 6 — FastAPI Layer

### Step 6.1 — Main application

Create `services/orchestration/main.py`:

```python
"""
services/orchestration/main.py
FastAPI application with lifespan management.
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from session.redis_client import SessionManager
from session.models import PMAgentState
from context_loader.s3_loader import load_company_context, invalidate_cache
from tools.deps import build_deps, _get_process_aha_client


session_manager = SessionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: warm singletons
    lc = _get_lambda_client()
    print(f"LambdaClient ready")
    yield


app = FastAPI(title="PMM AI Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Tighten to CloudFront domain in prod
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ── Request/response models ───────────────────────────────────────────────────

class StartRequest(BaseModel):
    pm_name: str   # from frontend dropdown: "Prasanth Sai", "Aiushe Mishra", "Carlos España", "Varsha Thalange"
    mode:    str   # "release" | "adhoc"

class EndRequest(BaseModel):
    reason: str = "completed"   # "completed" | "restarted"

class RespondRequest(BaseModel):
    input: str

    @validator("input")
    def sanitize_input(cls, v):
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
        import re
        for pattern in injection_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Input contains disallowed content")
        return v.strip()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "1.0.0"}


@app.post("/sessions/start")
async def start_session(req: StartRequest):
    pm_context  = load_company_context_by_name(req.pm_name)  # maps name → email → PMContext
    session_id  = str(uuid.uuid4())
    state       = PMAgentState(
        session_id=session_id,
        pm_name=req.pm_name,
        pm_context=pm_context,
        mode=req.mode,
        current_node="EntryNode",
        start_time=datetime.utcnow().isoformat(),
    )
    deps = build_deps(pm_context, session_id)

    # Run graph until HITL pause or completion
    from graph.graph import pmm_graph, is_hitl_node, EntryNode
    from pydantic_graph import End

    try:
        async with pmm_graph.iter(EntryNode(), state=state, deps=deps) as graph_run:
            node = graph_run.next_node
            while not isinstance(node, End):
                node = await graph_run.next(node)
                if is_hitl_node(node):
                    # HITL pause — save state, return message to PM
                    state.current_node = type(node).__name__
                    await session_manager.save(session_id, state)
                    return {
                        "session_id":     session_id,
                        "message":        state.last_message,
                        "awaiting_input": True,
                    }
    except Exception as e:
        import structlog
        structlog.get_logger().error("graph_error", session_id=session_id, error=str(e))
        await session_manager.save(session_id, state)
        return {"session_id": session_id, "message": f"Error: {str(e)}. You can retry.", "awaiting_input": True}

    # Graph completed without HITL pause
    await session_manager.save(session_id, state)
    return {"session_id": session_id, "message": state.last_message, "awaiting_input": False}


@app.post("/sessions/{session_id}/respond")
async def respond(session_id: str, req: RespondRequest):
    state = await session_manager.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    state.pm_input = req.input
    deps = build_deps(state.pm_context, session_id, state.release_label)

    # Resume graph from current node
    from graph.graph import pmm_graph, is_hitl_node, get_node_class
    from pydantic_graph import End

    current_node_cls = get_node_class(state.current_node)

    try:
        async with pmm_graph.iter(current_node_cls(), state=state, deps=deps) as graph_run:
            node = graph_run.next_node
            while not isinstance(node, End):
                node = await graph_run.next(node)
                if is_hitl_node(node):
                    state.current_node = type(node).__name__
                    state.pm_input = None
                    await session_manager.save(session_id, state)
                    return {"message": state.last_message, "awaiting_input": True}
    except Exception as e:
        import structlog
        structlog.get_logger().error("graph_error", session_id=session_id, error=str(e))
        await session_manager.save(session_id, state)
        return {"message": f"Error: {str(e)}. You can retry.", "awaiting_input": True}

    # Graph completed (DoneNode returned End)
    from session.session_history import save_session_record
    await save_session_record(state, "completed")
    await session_manager.delete(session_id)
    return {"message": state.last_message, "awaiting_input": False}


@app.get("/sessions/{session_id}/status")
async def status(session_id: str):
    state = await session_manager.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id":   state.session_id,
        "current_node": state.current_node,
        "mode":         state.mode,
        "pm_context":   state.pm_context.model_dump() if state.pm_context else None,
        "release_label": state.release_label,
    }


@app.post("/sessions/{session_id}/end")
async def end_session(session_id: str, req: EndRequest):
    """End session: write history to DynamoDB, clean up Redis. Called by restart button or DoneNode."""
    state = await session_manager.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    from session.session_history import save_session_record
    await save_session_record(state, status=req.reason)
    await session_manager.delete(session_id)
    return {"ended": True, "session_id": session_id, "status": req.reason}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    state = await session_manager.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    await session_manager.delete(session_id)
    return {"deleted": True}


@app.post("/internal/context/invalidate")
async def invalidate_context(body: dict):
    invalidate_cache()
    return {"invalidated": True, "key": body.get("key")}


@app.get("/internal/tools/list")
async def list_tools():
    from config.skills.aha.tools import AHA_TOOLS
    from config.skills.egain.tools import EGAIN_TOOLS
    return {"tools": [t.__name__ for t in AHA_TOOLS] + [t.__name__ for t in EGAIN_TOOLS]}


# Graph is constructed in graph/graph.py — see Step 5.13. No dispatch() needed.
```

**Checkpoint 6.1:** With Redis running:

```bash
cd services/orchestration
uvicorn main:app --reload --port 8000 &
sleep 3

# Test health
curl -s http://localhost:8000/health | python3 -m json.tool

# Test tools list
curl -s http://localhost:8000/internal/tools/list | python3 -m json.tool

# Test session start (requires valid PM email in your company-context.md)
curl -s -X POST http://localhost:8000/sessions/start \
  -H "Content-Type: application/json" \
  -d '{"pm_name":"Prasanth Sai","mode":"release"}' \
  | python3 -m json.tool

kill %1
```

All three should return valid JSON. The session start will return a `session_id` and a greeting message.

---


---

## Section 7b — Lambdas: Generic Skill Client + Context Refresher

### Step 7b.1 — Lambda architecture overview

There are two Lambdas in this project:

| Lambda | Purpose | Trigger |
|---|---|---|
| `pmm-skill-client` | **Generic skill executor for ALL API integrations.** Reads `api_config` from the invocation payload to determine auth strategy. Handles `basic` auth (Secrets Manager) and `basic_onbehalf` auth (Secrets Manager credentials sent as query params). | `boto3 lambda.invoke` from orchestration service |
| `pmm-context-refresher` | Invalidates company-context cache on S3 update | S3 `ObjectCreated` event |

The `pmm-skill-client` Lambda is generic — adding a new skill (Jira, Mailchimp, etc.) requires zero Lambda code changes. Just add a new `tools.py` with the right `API_CONFIG` constant. Each invocation is stateless — no connection pools, no shared rate limiters. If an external API returns 429, the error propagates to the agent and is surfaced to the PM.

The context-refresher Lambda fires immediately on S3 `ObjectCreated` events and tells the ECS service to drop its cache — so the new context takes effect within seconds, not 5 minutes.

### Step 7b.2 — Create the handler

Create `lambdas/context-refresher/handler.py`:

```python
import os
import httpx


def handler(event, context):
    """
    Triggered by S3 ObjectCreated event on the context/ prefix.
    Calls POST /internal/context/invalidate on the orchestration service
    so the running process drops its company-context.md cache immediately.
    """
    orchestration_url = os.environ["ORCHESTRATION_INTERNAL_URL"]
    for record in event.get("Records", []):
        key = record["s3"]["object"]["key"]
        try:
            r = httpx.post(
                f"{orchestration_url}/internal/context/invalidate",
                json={"key": key},
                timeout=10,
            )
            r.raise_for_status()
            print(f"Cache invalidated for key: {key}")
        except Exception as e:
            print(f"Failed to invalidate cache for {key}: {e}")
            raise
    return {"statusCode": 200}
```

Create `lambdas/context-refresher/requirements.txt`:

```
httpx>=0.27.0
```

### Step 7b.2b — Create the generic skill client Lambda

Create `lambdas/skill-client/handler.py`:

```python
"""
lambdas/skill-client/handler.py

Generic skill executor Lambda — handles ALL skill API calls.
Auth strategy is read from api_config (passed in the invocation payload),
which comes from each skill's API_CONFIG constant in tools.py.

Supported auth types:
  basic           → Secrets Manager → Basic auth header
  basic_onbehalf  → Secrets Manager → credentials passed as query params
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any

import boto3
import httpx


def handler(event, context):
    api_config = event["api_config"]

    # 1. Resolve auth headers
    auth_headers = _resolve_auth(api_config)

    # 2. Build base URL
    base_url = _resolve_base_url(api_config)

    # 3. Path is already resolved by the tool function in tools.py
    path = event["path"]

    # Skill-specific path adjustments (e.g. AIA tag-based fetch)
    path = _apply_skill_path_overrides(api_config["name"], path, event["params"])

    # 4. All params are passed through — the tool function decides what to send
    params = {k: v for k, v in event["params"].items() if v is not None}

    # 5. Make the API call
    method = event["method"]
    with httpx.Client(base_url=base_url, headers=auth_headers, timeout=30.0) as http:
        if method == "GET":
            r = http.request(method, path, params=params)
        else:
            r = http.request(method, path, json=params)
        r.raise_for_status()
        return {"statusCode": 200, "body": r.json()}


# ── Auth resolution ──────────────────────────────────────────────────────────

def _resolve_auth(api_config: dict) -> dict:
    auth = api_config["auth"]

    if auth["type"] == "basic":
        sm = boto3.client("secretsmanager", region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        secret = json.loads(sm.get_secret_value(SecretId=auth["credentials_secret"])["SecretString"])
        api_key = secret[auth["secret_field"]]
        token = base64.b64encode(f"{api_key}:".encode()).decode()
        return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

    elif auth["type"] == "basic_onbehalf":
        # Credentials are passed as query params by the caller; no auth header needed.
        return {"Content-Type": "application/json"}

    raise ValueError(f"Unknown auth type: {auth['type']}")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _resolve_base_url(api_config: dict) -> str:
    url = api_config["base_url"]
    # Replace template vars with env vars
    if "{subdomain}" in url:
        url = url.replace("{subdomain}", os.environ.get("AHA_SUBDOMAIN", "egain"))
    if "{egain_host}" in url:
        url = url.replace("{egain_host}", os.environ.get("EGAIN_API_HOST", "apidev.egain.com"))
    return url


def _apply_skill_path_overrides(skill_name: str, path: str, params: dict) -> str:
    """Skill-specific path adjustments (e.g. AIA tag-based fetch)."""
    if skill_name == "aha":
        if "product_key" in params and "tag" in params and "release_id" not in params:
            return f"/products/{params['product_key']}/features"
    return path
```

Create `lambdas/skill-client/requirements.txt`:

```
httpx>=0.27.0
boto3>=1.34.0
redis>=5.0.0
```

---

### Step 7b.3 — Configure Lambdas in Terraform

Add to `infrastructure/terraform/modules/lambda/main.tf`:

```hcl
# ── Generic Skill Client Lambda ──────────────────────────────────────────────

resource "aws_lambda_function" "skill_client" {
  function_name = "pmm-skill-client"
  handler       = "handler.handler"
  runtime       = "python3.11"
  filename      = "skill_client.zip"
  timeout       = 30
  memory_size   = 256
  environment {
    variables = {
      AHA_SUBDOMAIN      = var.aha_subdomain
      EGAIN_API_HOST     = var.egain_api_host
      AWS_DEFAULT_REGION = var.aws_region
    }
  }
}

# ── Context Refresher Lambda ──────────────────────────────────────────────────

resource "aws_lambda_function" "context_refresher" {
  function_name = "pmm-context-refresher"
  handler       = "handler.handler"
  runtime       = "python3.11"
  filename      = "context_refresher.zip"
  environment {
    variables = {
      ORCHESTRATION_INTERNAL_URL = var.orchestration_internal_url
    }
  }
}

resource "aws_s3_bucket_notification" "context_trigger" {
  bucket = var.context_bucket_id
  lambda_function {
    lambda_function_arn = aws_lambda_function.context_refresher.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "context/"
  }
}
```

**Note:** The `pmm-skill-client` Lambda does not require VPC access — all external API calls go over the public internet via the Lambda NAT gateway.

### Step 7b.4 — Deploy and verify

```bash
# Package and deploy all Lambdas
for lambda_dir in skill-client context-refresher; do
  cd lambdas/$lambda_dir
  pip install -r requirements.txt -t ./package
  cp *.py ./package/
  cd package && zip -r ../${lambda_dir}.zip . && cd ..
  aws lambda update-function-code \
    --function-name pmm-${lambda_dir} \
    --zip-file fileb://${lambda_dir}.zip
  cd ../..
done
```

**Checkpoint 7b:** Update `context/company-context.md` (change a release date), push to S3, then check CloudWatch Logs for the Lambda. Within 30 seconds the orchestration service logs should show `Cache invalidated for key: context/company-context.md`.

```bash
# Test context-refresher manually
aws s3 cp context/company-context.md s3://${BUCKET_NAME}/company-context.md
aws logs tail /aws/lambda/pmm-context-refresher --follow

# Test skill-client Lambda with Aha (basic auth)
aws lambda invoke --function-name pmm-skill-client \
  --payload '{"method":"GET","path":"/products/AIA/releases","params":{"product_key":"AIA"},"api_config":{"name":"aha","base_url":"https://{subdomain}.aha.io/api/v1","auth":{"type":"basic","credentials_secret":"pmm-agent/aha-api-key","secret_field":"api_key"}}}' \
  /dev/stdout
```

---
## Section 7 — Dockerfile and Local Docker Build

### Step 7.1 — Dockerfile

Create `services/orchestration/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health').raise_for_status()"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

```bash
# Build and test locally
docker compose build orchestration
docker compose up -d
sleep 5

# Verify both services are healthy
docker compose ps
curl -s http://localhost:8000/health

docker compose down
```

**Checkpoint 7.1:** `docker compose ps` shows both `orchestration` and `redis` as healthy (green). `/health` returns `{"status":"healthy"}`.

---

---

## Section 8 — Test Suite

Build and run the full test suite. Do this **before** deploying to dev — tests are your safety net against regressions.

### Step 8.1 — Install test dependencies

```bash
uv pip install pytest pytest-asyncio pytest-cov httpx respx
```

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "httpx>=0.27",
    "respx>=0.21",
]
```

### Step 8.2 — Create shared fixtures (`tests/conftest.py`)

```python
import json, os, uuid
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ── CLI options ───────────────────────────────────────────────────────────────
def pytest_addoption(parser):
    parser.addoption("--run-live",  action="store_true", default=False)
    parser.addoption("--base-url",  default="http://localhost:8000")
    parser.addoption("--env",       default="local")

@pytest.fixture(scope="session")
def run_live(request): return request.config.getoption("--run-live")

@pytest.fixture(scope="session")
def base_url(request): return request.config.getoption("--base-url")

# ── Environment ───────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def set_test_env(monkeypatch):
    monkeypatch.setenv("AHA_SUBDOMAIN",              "egain")
    monkeypatch.setenv("AHA_API_KEY_OVERRIDE",       "test-aha-key")
    monkeypatch.setenv("EGAIN_API_HOST",              "apidev.egain.com")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("CONTEXT_BUCKET",             "test-context-bucket")
    monkeypatch.setenv("AWS_DEFAULT_REGION",         "us-east-1")

# ── AWS mock (autouse — never hits real AWS in unit tests) ────────────────────
@pytest.fixture(autouse=True)
def mock_secrets_manager():
    with patch("boto3.client") as mock_client:
        mock_sm = MagicMock()
        mock_sm.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "test-key"})
        }
        mock_client.return_value = mock_sm
        yield mock_sm

# ── Redis mock ────────────────────────────────────────────────────────────────
@pytest.fixture
def mock_redis():
    store = {}
    mock = AsyncMock()
    mock.get.side_effect     = lambda k: store.get(k)
    mock.setex.side_effect   = lambda k, ttl, v: store.update({k: v})
    mock.delete.side_effect  = lambda k: store.pop(k, None)
    mock.exists.side_effect  = lambda k: k in store
    return mock, store

# ── Fixture data ──────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def aha_fixtures():
    with open("tests/fixtures/mock_aha_responses.json") as f:
        return json.load(f)

@pytest.fixture(scope="session")
def egain_fixtures():
    with open("tests/fixtures/mock_egain_responses.json") as f:
        return json.load(f)

@pytest.fixture(scope="session")
def mock_company_context():
    with open("tests/fixtures/mock_company_context.md") as f:
        return f.read()

@pytest.fixture
def session_id():
    return str(uuid.uuid4())
```

### Step 8.3 — Create test fixtures

Create `tests/fixtures/mock_company_context.md` — copy from `context/company-context.md` (your real one). This is the version the unit tests use.

Create `tests/fixtures/mock_state.py`:

```python
from session.models import (
    PMAgentState, PMContext, AhaMapping, ArticlePlan,
    IteratorState, DocumentPlan
)

def make_pm_context(email="prasanth.sai@egain.com") -> PMContext:
    return PMContext(
        pm_id="prasanth.sai",
        name="Prasanth Sai",
        owned_products=["AIA", "ECAI"],
        aha_mappings={
            "AIA":  AhaMapping(product="AI Agent",    aha_product_key="AIA",
                               release_field_type="aia_version_tag",
                               aia_version_prefix="AIA"),
            "ECAI": AhaMapping(product="AI Services", aha_product_key="ECAI",
                               release_field_type="standard_release"),
        },
        portal_context={"AIA": {"portal_id": "1001", "portal_name": "eGain AI Agent Knowledge Portal", "topics": [{"name": "AIA Release Notes", "id": "topic_001"}]}},
        release_cadence_rules="AIA uses version tags. ECAI uses YY.MM.",
        upcoming_releases=[{"release": "AIA 1.2.0", "products": "AIA", "target": "Mar 2025"}],
    )

def make_agent_state(pm_name="Prasanth Sai", pm_email="prasanth.sai@egain.com", **kwargs) -> PMAgentState:
    return PMAgentState(
        session_id=kwargs.pop("session_id", "test-session-001"),
        pm_name=pm_name,
        pm_context=make_pm_context(pm_email),
        start_time=kwargs.pop("start_time", "2026-03-18T10:00:00"),
        **kwargs
    )

def make_article_plan(article_id=None, **kwargs) -> ArticlePlan:
    return ArticlePlan(
        title=kwargs.pop("title", "Test Article"),
        article_id=article_id,
        planned_changes=kwargs.pop("planned_changes", "Update section 2."),
        jira_url=kwargs.pop("jira_url", "https://egain.atlassian.net/browse/ECAI-123"),
        **kwargs
    )

def make_iterator_with_articles(n: int, confirmed: int = 0) -> IteratorState:
    articles = [make_article_plan(article_id=f"article-{i}", title=f"Article {i}") for i in range(n)]
    for i in range(confirmed):
        articles[i].confirmed = True
    return IteratorState(
        articles=articles,
        current_index=confirmed,
        confirmed_articles=[a for a in articles if a.confirmed],
    )
```

### Step 8.4 — Key unit tests to write

**eGain read-only API test — write this first:**

Create `tests/unit/egain/test_egain_read.py`:

```python
import pytest, json
import httpx
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_articles_in_topic_returns_list():
    """Verify egain_get_articles_in_topic parses response correctly."""
    import sys; sys.path.insert(0, "services/orchestration")

    fake_response = {
        "articles": [
            {"id": "10234", "title": "AIA 1.2.0 Release Notes", "status": "published",
             "updated_at": "2025-02-15", "summary": "Release notes for AIA 1.2.0..."},
            {"id": "10235", "title": "AIA Getting Started", "status": "published",
             "updated_at": "2025-01-10", "summary": "Getting started guide..."},
        ]
    }

    async def fake_invoke(lambda_name, payload):
        assert lambda_name == "pmm-skill-client"
        assert payload["method"] == "GET"
        assert "getarticlesintopic" in payload["path"]
        assert payload["params"]["portalId"] == "1001"
        assert payload["params"]["topicId"] == "topic_001"
        assert payload["api_config"]["auth"]["type"] == "basic_onbehalf"
        return fake_response["articles"]

    from tools.deps import LambdaClient
    client = LambdaClient()
    client.invoke_skill_lambda = AsyncMock(side_effect=fake_invoke)

    result = await client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": "/article/getarticlesintopic",
        "params": {"portalId": "1001", "topicId": "topic_001"},
        "api_config": {"auth": {"type": "basic_onbehalf"}},
    })

    assert len(result) == 2
    assert result[0]["title"] == "AIA 1.2.0 Release Notes"

@pytest.mark.asyncio
async def test_get_article_by_id_returns_content():
    """Verify egain_get_article_by_id returns full HTML content."""
    fake_article = {
        "id": "10234", "title": "AIA 1.2.0 Release Notes",
        "status": "published", "content_html": "<h2>What's New</h2><p>...</p>",
        "topic_id": "topic_001", "updated_at": "2025-02-15"
    }

    async def fake_invoke(lambda_name, payload):
        assert payload["params"]["articleId"] == "10234"
        return fake_article

    from tools.deps import LambdaClient
    client = LambdaClient()
    client.invoke_skill_lambda = AsyncMock(side_effect=fake_invoke)

    result = await client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": "/article/getarticlebyid",
        "params": {"portalId": "1001", "articleId": "10234"},
        "api_config": {"auth": {"type": "basic_onbehalf"}},
    })

    assert result["content_html"].startswith("<h2>")
    assert result["id"] == "10234"

@pytest.mark.asyncio
async def test_no_write_tools_registered():
    """Verify that no write tools (create, update, delete) are registered for eGain."""
    from config.skills.egain.tools import EGAIN_TOOLS
    assert len(EGAIN_TOOLS) == 2, f"Expected 2 read-only tools, got {len(EGAIN_TOOLS)}"
    # All eGain tool functions should only make GET requests (read-only)
    for tool_fn in EGAIN_TOOLS:
        assert "GET" in tool_fn.__doc__ or "read" in tool_fn.__doc__.lower(), \
            f"eGain tool {tool_fn.__name__} should be read-only"
```

**OutputNode recommendation test:**

Create `tests/unit/orchestration/test_output_node.py`:

```python
import pytest
from session.models import ArticlePlan
from graph.nodes.output_agent import OutputArticle

def test_output_article_recommendation_values():
    """Verify OutputArticle only allows valid recommendation values."""
    # Valid recommendations
    for rec in ("create", "update", "both"):
        art = OutputArticle(
            title="Test", recommendation=rec, reasoning="test",
            html_content="<p>content</p>",
        )
        assert art.recommendation == rec

def test_output_article_update_has_article_id():
    """Update recommendations should include article_id and target_article."""
    art = OutputArticle(
        title="AIA Release Notes",
        article_id="10234",
        recommendation="update",
        reasoning="Existing article matches closely",
        html_content="<h2>Updated</h2>",
        target_article="AIA 1.1.0 Release Notes",
    )
    assert art.article_id == "10234"
    assert art.target_article is not None

def test_output_article_create_has_no_article_id():
    """Create recommendations should have no article_id."""
    art = OutputArticle(
        title="New Feature Guide",
        recommendation="create",
        reasoning="No existing article covers this topic",
        html_content="<h2>New Guide</h2>",
    )
    assert art.article_id is None
```

**Session persistence test:**

Create `tests/unit/orchestration/test_session.py`:

```python
import pytest, sys
sys.path.insert(0, "services/orchestration")

from session.models import PMAgentState

@pytest.mark.asyncio
async def test_save_and_get_round_trip(mock_redis):
    mock, store = mock_redis
    from session.redis_client import SessionManager
    sm = SessionManager()
    sm._redis = mock

    state = PMAgentState(session_id="s-001", mode="release", current_node="PlanGenNode")
    await sm.save("s-001", state)

    loaded = await sm.get("s-001")
    assert loaded.session_id == "s-001"
    assert loaded.mode == "release"
    assert loaded.current_node == "PlanGenNode"

@pytest.mark.asyncio
async def test_ttl_is_24_hours(mock_redis):
    mock, _ = mock_redis
    from session.redis_client import SessionManager
    sm = SessionManager()
    sm._redis = mock

    state = PMAgentState(session_id="s-002")
    await sm.save("s-002", state)

    # setex called with TTL = 86400
    call_args = mock.setex.call_args_list[-1]
    assert call_args[0][1] == 86400, f"TTL must be 86400s (24h), got {call_args[0][1]}"

@pytest.mark.asyncio
async def test_two_sessions_dont_overwrite(mock_redis):
    mock, store = mock_redis
    from session.redis_client import SessionManager
    sm = SessionManager()
    sm._redis = mock

    s1 = PMAgentState(session_id="s-A", mode="release")
    s2 = PMAgentState(session_id="s-B", mode="adhoc")
    await sm.save("s-A", s1)
    await sm.save("s-B", s2)

    loaded_a = await sm.get("s-A")
    loaded_b = await sm.get("s-B")
    assert loaded_a.mode == "release"
    assert loaded_b.mode == "adhoc"

@pytest.mark.asyncio
async def test_redis_key_format(mock_redis):
    mock, _ = mock_redis
    from session.redis_client import SessionManager
    sm = SessionManager()
    sm._redis = mock

    await sm.save("abc-123", PMAgentState(session_id="abc-123"))
    set_key = mock.setex.call_args_list[-1][0][0]
    assert set_key == "session:abc-123", f"Key must be 'session:{{id}}', got '{set_key}'"
```

**Iterator loop test:**

Create `tests/unit/orchestration/test_update_iterator.py`:

```python
import pytest, sys, asyncio
sys.path.insert(0, "services/orchestration")
from tests.fixtures.mock_state import make_agent_state, make_iterator_with_articles
from unittest.mock import AsyncMock, patch

CONFIRM_PHRASES = ["confirm", "yes", "ok", "looks good", "approved", "LGTM", "lgtm", "proceed"]

@pytest.mark.asyncio
@pytest.mark.parametrize("phrase", CONFIRM_PHRASES)
async def test_confirm_phrases_route_to_advance(phrase):
    state = make_agent_state()
    state.update_iterator = make_iterator_with_articles(3)

    with patch("pydantic_ai.Agent.run") as mock_run:
        from session.models import IteratorState
        mock_result = AsyncMock()
        mock_result.output.next_node = "AdvanceUpdateIndex"
        mock_result.output.message   = "Confirmed."
        mock_result.output.awaiting_input = False
        mock_result.output.refined_content = None
        mock_run.return_value = mock_result

        from graph.nodes.update_iterator import run_update_feedback_gate
        # Build minimal deps
        from tests.fixtures.mock_state import make_pm_context
        result = await run_update_feedback_gate(state, None, phrase)  # type: ignore

@pytest.mark.asyncio
async def test_full_3_article_loop():
    state = make_agent_state()
    state.update_iterator = make_iterator_with_articles(3)

    from graph.nodes.update_iterator import run_advance_update_index

    class FakeDeps:
        pass

    # Advance through all 3 articles
    r1 = await run_advance_update_index(state, FakeDeps())
    assert state.update_iterator.current_index == 1
    assert r1.next_node == "ShowUpdatePlan"

    r2 = await run_advance_update_index(state, FakeDeps())
    assert state.update_iterator.current_index == 2
    assert r2.next_node == "ShowUpdatePlan"

    state.mode_order = ["updates", "creates"]
    state.create_iterator = make_iterator_with_articles(0)  # no creates
    r3 = await run_advance_update_index(state, FakeDeps())
    assert r3.next_node == "OutputAgentNode"  # all done
```

### Step 8.5 — Run the tests

```bash
# Run unit tests only (fast, no network)
pytest tests/unit/ -v --tb=short

# Run with coverage
pytest tests/unit/ tests/functional/ \
  --cov=services/orchestration \
  --cov-report=term-missing \
  --cov-fail-under=80

# What passing looks like:
# tests/unit/egain/test_drafts.py::test_create_draft_always_sets_source_and_status PASSED
# tests/unit/orchestration/test_session.py::test_save_and_get_round_trip PASSED
# tests/unit/orchestration/test_session.py::test_ttl_is_24_hours PASSED
# ...
# Coverage: 82% — PASSED (target: ≥80%)
```

**Checkpoint 8:** All unit tests pass. Coverage ≥ 80%. If any test fails, fix it before deploying — every test failure caught here is a production bug avoided.

### Step 8.6 — Test layers summary

| Layer | Command | Speed | Use when |
|---|---|---|---|
| Unit | `pytest tests/unit/ -v` | ~10s | Every code change |
| Functional | `pytest tests/functional/ -v` | ~30s | Before PR |
| Integration | `pytest tests/integration/ --run-live` | ~2min | After merging to dev |
| Smoke | `pytest tests/smoke/ --base-url=https://dev-alb` | ~90s | After every deploy |
| E2E | `pytest tests/e2e/ --run-live --base-url=...` | ~5min | Pre-release |

---
## Section 9 — Deploy to Dev

### Step 9.1 — Upload company-context.md to S3

```bash
BUCKET_NAME="egain-pmm-agent-context-$(aws sts get-caller-identity --query Account --output text)"

aws s3 cp context/company-context.md s3://${BUCKET_NAME}/company-context.md
echo "Uploaded. Verify:"
aws s3 ls s3://${BUCKET_NAME}/
```

**Checkpoint 9.1:** File appears in S3 with current timestamp.

---

### Step 9.2 — Push Docker image to ECR

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"
IMAGE_TAG=$(git rev-parse --short HEAD)

# Authenticate
aws ecr get-login-password --region us-east-1 \
  | docker login --username AWS --password-stdin "${ECR_REGISTRY}"

# Build, tag, push
docker build -t pmm-orchestration services/orchestration/
docker tag pmm-orchestration:latest "${ECR_REGISTRY}/pmm-orchestration:${IMAGE_TAG}"
docker tag pmm-orchestration:latest "${ECR_REGISTRY}/pmm-orchestration:latest"
docker push "${ECR_REGISTRY}/pmm-orchestration:${IMAGE_TAG}"
docker push "${ECR_REGISTRY}/pmm-orchestration:latest"

echo "Pushed: ${ECR_REGISTRY}/pmm-orchestration:${IMAGE_TAG}"
```

**Checkpoint 9.2:** `aws ecr describe-images --repository-name pmm-orchestration` shows your image tag.

---

### Step 9.3 — Create ECS task definition

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REGISTRY="${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com"
BUCKET_NAME="egain-pmm-agent-context-${ACCOUNT_ID}"
REDIS_ENDPOINT=$(cd infrastructure/terraform && terraform output -raw redis_endpoint)

# Register task definition
aws ecs register-task-definition --cli-input-json "{
  \"family\": \"pmm-orchestration\",
  \"networkMode\": \"awsvpc\",
  \"requiresCompatibilities\": [\"FARGATE\"],
  \"cpu\": \"1024\",
  \"memory\": \"2048\",
  \"executionRoleArn\": \"arn:aws:iam::${ACCOUNT_ID}:role/pmm-agent-ecs-execution\",
  \"taskRoleArn\": \"arn:aws:iam::${ACCOUNT_ID}:role/pmm-agent-ecs-task\",
  \"containerDefinitions\": [{
    \"name\": \"pmm-orchestration\",
    \"image\": \"${ECR_REGISTRY}/pmm-orchestration:latest\",
    \"portMappings\": [{\"containerPort\": 8000}],
    \"environment\": [
      {\"name\": \"APP_ENV\", \"value\": \"dev\"},
      {\"name\": \"REDIS_URL\", \"value\": \"redis://${REDIS_ENDPOINT}:6379\"},
      {\"name\": \"AHA_SUBDOMAIN\", \"value\": \"egain\"},
      {\"name\": \"EGAIN_API_HOST\", \"value\": \"apidev.egain.com\"},
      {\"name\": \"CONTEXT_BUCKET\", \"value\": \"${BUCKET_NAME}\"},
      {\"name\": \"AWS_DEFAULT_REGION\", \"value\": \"us-east-1\"}
    ],
    \"logConfiguration\": {
      \"logDriver\": \"awslogs\",
      \"options\": {
        \"awslogs-group\": \"/ecs/pmm-orchestration\",
        \"awslogs-region\": \"us-east-1\",
        \"awslogs-stream-prefix\": \"ecs\"
      }
    },
    \"healthCheck\": {
      \"command\": [\"CMD-SHELL\", \"curl -f http://localhost:8000/health || exit 1\"],
      \"interval\": 30, \"timeout\": 10, \"retries\": 3
    }
  }]
}"
```

---

### Step 9.4 — Create and start ECS service

```bash
CLUSTER=$(cd infrastructure/terraform && terraform output -raw ecs_cluster_name)
SUBNETS=$(cd infrastructure/terraform && terraform output -raw private_subnet_ids)
SG=$(cd infrastructure/terraform && terraform output -raw orchestration_sg_id)

aws ecs create-service \
  --cluster "${CLUSTER}" \
  --service-name pmm-orchestration \
  --task-definition pmm-orchestration \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SG}],assignPublicIp=DISABLED}"

# Wait for service to stabilise
aws ecs wait services-stable \
  --cluster "${CLUSTER}" \
  --services pmm-orchestration

echo "Service is running"
```

**Checkpoint 9.4:** `aws ecs describe-services --cluster ${CLUSTER} --services pmm-orchestration` shows `runningCount: 1` and `status: ACTIVE`.

---

### Step 9.5 — Run smoke tests

```bash
ALB_DNS=$(cd infrastructure/terraform && terraform output -raw public_alb_dns_name)

# Quick manual smoke test
curl -s "http://${ALB_DNS}/health"
# Expected: {"status":"healthy","version":"1.0.0"}

curl -s "http://${ALB_DNS}/internal/tools/list"
# Expected: {"tools":["aha_list_releases","aha_get_release_features",...]}

# Run the automated smoke suite
pytest tests/smoke/ \
  --base-url="http://${ALB_DNS}" \
  --env=dev \
  -v
```

**Checkpoint 9.5:** All smoke tests pass. The `/health` and `/internal/tools/list` endpoints return correct data.

---

---

## Section 9b — Observability

Do this **before** handing to PMs. You need to see what the agent is doing when PMs use it.

### Step 9b.1 — Structured logging

Add `structlog` to `requirements.txt`:

```
structlog>=24.0
```

Add to `services/orchestration/main.py` startup:

```python
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
log = structlog.get_logger()
```

Add entry/exit logging to every node runner. Example for `graph/graph.py`:

```python
log.info("node.enter", node=node, session_id=state.session_id,
         pm=state.pm_context.name if state.pm_context else None)
# ... run node ...
log.info("node.exit",  node=node, next_node=state.current_node,
         release=state.release_label)
```

### Step 9b.2 — Logfire (PydanticAI native tracing)

```bash
pip install logfire
```

Add to `main.py` lifespan startup:

```python
import logfire
logfire.configure()
logfire.instrument_pydantic_ai()   # traces all LLM calls + tool invocations
```

This gives you token usage per session, tool call latencies, and LLM response previews in the Logfire dashboard — invaluable for debugging why the agent made a bad plan.

### Step 9b.3 — CloudWatch dashboard

Create `infrastructure/scripts/create-dashboard.sh`:

```bash
aws cloudwatch put-dashboard --dashboard-name PMM-Agent-Dev --dashboard-body '{
  "widgets": [
    {"type": "metric", "properties": {
      "title": "ECS CPU/Memory",
      "metrics": [
        ["AWS/ECS", "CPUUtilization",    "ServiceName", "pmm-orchestration"],
        ["AWS/ECS", "MemoryUtilization", "ServiceName", "pmm-orchestration"]
      ]
    }},
    {"type": "log", "properties": {
      "title": "Session completions (DoneNode)",
      "query": "fields @timestamp, session_id, pm | filter next_node = \"DoneNode\" | stats count() by bin(1h)",
      "logGroupName": "/ecs/pmm-orchestration"
    }},
    {"type": "log", "properties": {
      "title": "Errors by node",
      "query": "fields @timestamp, node, session_id | filter level = \"error\" | stats count() by node",
      "logGroupName": "/ecs/pmm-orchestration"
    }}
  ]
}'
```

### Step 9b.4 — Rollout plan

| Week | Action |
|---|---|
| Week 1 | Deploy to dev. Run integration + smoke tests. Monitor Logfire for any tool errors. |
| Week 2 | Pilot with Prasanth Sai (most technically comfortable PM). Collect feedback on HITL prompts and plan quality. |
| Week 3 | Iterate on node instructions and plan generation based on pilot feedback. Update `SKILL.md` files as needed (no deploy required for skill text changes). |
| Week 4 | Roll out to all 7 PMs. 30-min walkthrough session. Share the frontend URL. |
| Ongoing | Update `context/company-context.md` each quarter for new releases. Add new skill folders for Phase 2 integrations (Jira, Mailchimp). |

---
## Section 10 — Frontend (S3 + CloudFront)

### Step 10.1 — Create frontend S3 bucket

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
FRONTEND_BUCKET="egain-pmm-agent-ui-${ACCOUNT_ID}"

aws s3api create-bucket --bucket "${FRONTEND_BUCKET}" --region us-east-1
aws s3 website --bucket "${FRONTEND_BUCKET}" \
  --index-document index.html --error-document index.html
```

### Step 10.2 — Deploy the chat widget

The `frontend/index.html` file (built in the DevOps plan) contains the full chat widget. Update the API URL:

```bash
# Set your ALB URL in the frontend config
sed -i "s|http://localhost:8000|http://${ALB_DNS}|g" frontend/index.html

# Upload to S3
aws s3 sync frontend/ s3://${FRONTEND_BUCKET}/ --delete

echo "Frontend URL: http://${FRONTEND_BUCKET}.s3-website-us-east-1.amazonaws.com"
```

**Checkpoint 10.2:** Opening the S3 website URL in a browser shows the eGain PMM Agent page and the chat launcher button.

---

## Section 11 — Git, CI/CD, and Production

### Step 11.1 — First commit

```bash
git add .
git commit -m "feat: initial PMM AI Agent implementation

- Skill folders: aha/, egain/, company-context/
- Service: FastAPI + PydanticAI + Redis sessions
- Concurrent session support: stateless Lambda invocations, per-session isolation via session_id
- AWS: ECS Fargate, ElastiCache Redis, S3 context, Secrets Manager
- Frontend: eGain-branded chat widget with SSE heartbeats"

git remote add origin git@github.com:egain/pmm-ai-agent.git
git push -u origin main
```

### Step 11.2 — Create dev branch

```bash
git checkout -b dev
git push -u origin dev
```

All feature development happens in `feature/*` branches → PR to `dev` → tested → PR to `main` → production deploy. See `pmm-ai-agent-devops-plan.md` for the full CI/CD workflow.

---

---

## Section 14 — Extension Guide

How to add new integrations without touching the graph or creating new services.

### Adding Jira context to release planning

Adds Jira issue details (acceptance criteria, test notes) to the release context gathering step.

```bash
# Step 1: Create the skill folder
mkdir -p config/skills/jira/{scripts,references}
```

Create `config/skills/jira/SKILL.md`:
```yaml
---
name: jira
description: >
  Use when fetching Jira issue details for Aha features during release context gathering.
  Call jira_get_issue to get acceptance criteria and test notes linked from Aha features.
---
# Jira Skill
## When to call
After fetching Aha features, call jira_get_issue for each feature that has a jira_url.
Extract: summary, description, acceptance_criteria, test_notes, status.
## Field paths
  issue.fields.summary
  issue.fields.description
  issue.fields.customfield_10016 (acceptance criteria — verify field ID in your Jira)
  issue.fields.status.name
```

Create `config/skills/jira/tools.py`:
```python
"""
config/skills/jira/tools.py

Jira tool functions — imported directly by agent nodes.
"""
from __future__ import annotations

from typing import Any
from pydantic_ai import RunContext

JIRA_API_CONFIG = {
    "name": "jira",
    "base_url": "https://egain.atlassian.net/rest/api/3",
    "auth": {
        "type": "basic",
        "credentials_secret": "pmm-agent/jira-credentials",
        "secret_field": "api_token",
    },
}


async def jira_get_issue(ctx: RunContext[AgentDeps], issue_key: str) -> Any:
    """Get full details for a Jira issue. Use after fetching Aha features
    to enrich each feature with acceptance criteria and test notes.

    Args:
        issue_key: Jira issue key, e.g. 'ECAI-456'.
    """
    return await ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", {
        "method": "GET",
        "path": f"/issue/{issue_key}",
        "params": {"issue_key": issue_key},
        "api_config": JIRA_API_CONFIG,
    })


JIRA_TOOLS = [jira_get_issue]
```

No new Lambda needed — `pmm-skill-client` reads auth config from `JIRA_API_CONFIG` in `tools.py`.

Then wire it in:
```python
# graph/nodes/release_context_agent.py — add Jira tools
from config.skills.jira.tools import JIRA_TOOLS

release_context_agent: Agent[AgentDeps, ReleaseContextResult] = Agent(
    deps_type=AgentDeps,
    result_type=ReleaseContextResult,
    tools=AHA_TOOLS + JIRA_TOOLS,
)
# add to @agent.instructions: "Also fetch jira_get_issue for each feature's jira_url"
```

**No graph changes. No new ECS service. No new Lambda. Just a new `tools.py`.**

---

### Adding Mailchimp email campaign output

Adds a Mailchimp campaign draft to the output step alongside portal article updates.

Create `config/skills/mailchimp/` with the same structure (SKILL.md, tools.py, scripts/mailchimp_client.py, references/api.md).

Wire into `OutputAgentNode`:
```python
from config.skills.mailchimp.tools import MAILCHIMP_TOOLS

output_agent: Agent[AgentDeps, OutputResult] = Agent(
    deps_type=AgentDeps, result_type=OutputResult,
    tools=MAILCHIMP_TOOLS,
)
# Update @agent.instructions to include:
# "Also call mailchimp_create_campaign with a summary of the release changes,
#  then call mailchimp_save_as_draft. Do this after publishing all portal drafts."
```

**No graph changes. One new skill folder. No new Lambda.**

---

### Adding a new PM or product

No code change. Just update `context/company-context.md` and push to S3:

```bash
# 1. Edit the file locally
#    Add the new PM row to the ownership table
#    Add the new product to the Aha mappings table if needed

# 2. Push to S3
aws s3 cp context/company-context.md s3://${BUCKET_NAME}/company-context.md

# 3. Cache clears automatically via Lambda within 30 seconds
# 4. New PM can log in immediately — no deploy required
```

---
## Quick Reference — Key Commands

```bash
# Local dev
docker compose up -d                                    # start Redis
uvicorn services/orchestration/main:app --reload       # run service

# Tests
pytest tests/unit/ -v                                  # unit tests
pytest tests/unit/ tests/functional/ --cov=services/  # with coverage
pytest tests/smoke/ --base-url=http://localhost:8000   # smoke (local)

# Deploy
docker compose build && docker compose push            # build + push to ECR
aws ecs update-service --cluster pmm-agent-dev \
  --service pmm-orchestration --force-new-deployment   # redeploy

# Skills
cat config/skills/aha/SKILL.md                        # view Aha skill
cat config/skills/aha/tools.py                         # view Aha tools

# Context
aws s3 cp context/company-context.md s3://${BUCKET}/  # update context
```

---

## Checklist — Before Handing to PMs

- [ ] `/health` endpoint returns 200 in dev
- [ ] `/internal/tools/list` shows all 6 tools (4 Aha + 2 eGain)
- [ ] Session start with `prasanth.sai@egain.com` returns a greeting mentioning AIA and ECAI
- [ ] Session start with `aiushe.mishra@egain.com` returns a greeting mentioning AIA only
- [ ] AIA release flow uses version tags, not Release field
- [ ] ECAI/ECKN/ECAD flow uses standard Release field
- [ ] eGain integration is read-only; agent presents HTML content to PM
- [ ] Smoke tests pass in dev
- [ ] `company-context.md` in S3 matches real PM org (Varsha, Aiushe, Prasanth, Carlos, Ankur, Peter, Kevin)
- [ ] Frontend chat widget accessible at CloudFront URL
- [ ] Two PMs can use the agent simultaneously (concurrent session test)
