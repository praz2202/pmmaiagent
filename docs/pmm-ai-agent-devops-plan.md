# PMM AI Agent — Local Dev, Git Workflow & Deployment Pipeline

**Project:** eGain PMM AI Agent  
**Version:** 2.0  
**Depends On:** `pmm-ai-agent-guide.md`

---

## Table of Contents

1. [Local Development Environment Setup](#1-local-development-environment-setup)
2. [Git Repository Structure & Branching Strategy](#2-git-repository-structure--branching-strategy)
3. [Pre-Push Test Gates](#3-pre-push-test-gates)
4. [CI/CD Pipeline — Dev Environment](#4-cicd-pipeline--dev-environment)
5. [CI/CD Pipeline — Production Environment](#5-cicd-pipeline--production-environment)
6. [Post-Deploy Smoke Tests](#6-post-deploy-smoke-tests)
7. [Bug Triage & Hotfix Flow](#7-bug-triage--hotfix-flow)
8. [Frontend (S3 + CloudFront) Deployment](#8-frontend-s3--cloudfront-deployment)
9. [Environment Configuration Reference](#9-environment-configuration-reference)

---

## 1. Local Development Environment Setup

### 1.1 First-Time Setup

Clone the repo and bootstrap your local environment:

```bash
git clone git@github.com:egain/pmm-ai-agent.git
cd pmm-ai-agent

# Install Python deps for all services using uv
pip install uv
uv sync --all-packages

# Copy environment files
cp .env.example .env.local
# Edit .env.local — add your personal Aha dev API key and local overrides
```

### 1.2 Local Environment File Structure

```
pmm-ai-agent/
├── .env.example          # Committed — safe defaults, no secrets
├── .env.local            # Git-ignored — your personal dev overrides
├── .env.dev              # Git-ignored — dev environment values (CI writes these)
└── .env.prod             # Git-ignored — prod values (CI only, never local)
```

`.env.example` contents (committed to repo):

```bash
# Application
APP_ENV=local
LOG_LEVEL=debug

# Redis (local Docker)
REDIS_URL=redis://localhost:6379


# AWS (local uses LocalStack or real dev account)
AWS_DEFAULT_REGION=us-east-1
AWS_PROFILE=pmm-agent-dev

# S3 Context Bucket (dev)
CONTEXT_BUCKET=egain-pmm-agent-context-dev

# Secrets — in local dev, these can be overridden with plaintext values
# In all other envs, these are read from AWS Secrets Manager
AHA_API_KEY_OVERRIDE=          # set locally to avoid Secrets Manager call
EGAIN_CLIENT_APP_OVERRIDE=    # eGain on-behalf-of-customer auth
EGAIN_CLIENT_SECRET_OVERRIDE=
GEMINI_API_KEY=                # default LLM provider
CLAUDE_API_KEY=                # Anthropic LLM provider (optional)
OPENAI_API_KEY=                # OpenAI LLM provider (optional)

# Frontend
ORCHESTRATION_API_URL=http://localhost:8000
```

### 1.3 Starting All Services Locally

```bash
# Start everything (Redis + all three services)
docker-compose up --build

# Or start individual services for faster iteration
docker-compose up redis                     # just Redis
docker-compose up redis                      # just Redis (no MCP servers in v2)
docker-compose up orchestration             # just the main app

# Watch logs for a specific service
docker-compose logs -f orchestration
```

### 1.4 Running Tests Locally

```bash
# Run all unit tests across all services
make test

# Run tests by layer
make test-unit
make test-functional
make test-orchestration

# Run with coverage report
make test-coverage

# Run linting and type checks
make lint
make typecheck
```

### 1.5 Makefile Reference

```makefile
# Makefile (root)

.PHONY: test test-coverage lint typecheck build push-dev

test:
	pytest tests/unit/ tests/functional/ \
	  -v --tb=short

test-unit:
	pytest tests/unit/ -v

test-functional:
	pytest tests/functional/ -v

test-orchestration:
	pytest services/orchestration/tests/ -v

test-coverage:
	pytest --cov=services --cov=lambdas --cov-report=html --cov-report=term-missing

lint:
	ruff check services/ lambdas/
	ruff format --check services/ lambdas/

typecheck:
	mypy services/orchestration

build:
	docker-compose build

push-dev:
	bash infrastructure/scripts/push-to-ecr.sh dev

push-prod:
	bash infrastructure/scripts/push-to-ecr.sh prod

upload-context-dev:
	aws s3 sync context/ s3://egain-pmm-agent-context-dev/ --profile pmm-agent-dev

upload-context-prod:
	aws s3 sync context/ s3://egain-pmm-agent-context-prod/ --profile pmm-agent-prod

deploy-frontend-dev:
	aws s3 sync frontend/ s3://egain-pmm-agent-ui-dev/ --delete
	aws cloudfront create-invalidation --distribution-id $CF_DIST_ID_DEV --paths "/*"

deploy-frontend-prod:
	aws s3 sync frontend/ s3://egain-pmm-agent-ui-prod/ --delete
	aws cloudfront create-invalidation --distribution-id $CF_DIST_ID_PROD --paths "/*"
```

---

## 2. Git Repository Structure & Branching Strategy

### 2.1 Branch Model

```
main (production)
│
└── dev (integration / staging)
    │
    ├── feature/TICKET-123-aha-skill-tool-fix
    ├── feature/TICKET-124-update-iterator-loop
    ├── fix/TICKET-125-aia-tag-parsing-bug
    └── chore/update-company-context-q4
```

| Branch | Deploys To | Protected | Who Merges |
|---|---|---|---|
| `main` | Production (ECS prod, S3 prod) | Yes — requires PR + passing CI | Tech Lead only |
| `dev` | Dev/Staging (ECS dev, S3 dev) | Yes — requires PR + passing CI | Any team member |
| `feature/*` | Local only | No | Developer |
| `fix/*` | Local only | No | Developer |
| `hotfix/*` | Prod directly (emergency only) | No — but still requires CI | Tech Lead only |

### 2.2 Day-to-Day Developer Workflow

```bash
# 1. Start from latest dev
git checkout dev
git pull origin dev

# 2. Create your feature branch
git checkout -b feature/TICKET-123-aha-skill-tool-fix

# 3. Write code and tests
# ... development work ...

# 4. Run local test gate (mandatory before push — see Section 3)
make test && make lint && make typecheck

# 5. Commit
git add .
git commit -m "feat(aha): add aha_list_releases tool with AIA tag support

- Implements aha_list_releases(product_key) with in_progress/planned filter
- Handles AIA version tag detection per company-context rules
- Adds mock fixtures for Aha releases API response
- 100% unit test coverage on new code

Refs: TICKET-123"

# 6. Push and open PR to dev
git push origin feature/TICKET-123-aha-skill-tool-fix
# Open PR in GitHub: feature/TICKET-123 → dev
```

### 2.3 Commit Message Convention

Follow Conventional Commits:

```
<type>(<scope>): <short description>

<body — optional, explains why not what>

Refs: TICKET-XXX
```

| Type | When to use |
|---|---|
| `feat` | New feature or tool |
| `fix` | Bug fix |
| `test` | Adding or fixing tests |
| `chore` | Dependency updates, config, non-code changes |
| `docs` | Documentation updates (including skill MDs) |
| `refactor` | Code restructure, no behavior change |
| `perf` | Performance improvement |
| `ci` | CI/CD pipeline changes |

### 2.4 PR Requirements Before Merge to `dev`

All of these must pass before a PR can merge to `dev`:

- [ ] CI unit tests pass (GitHub Actions — see Section 4)
- [ ] Lint passes (ruff)
- [ ] Type checks pass (mypy)
- [ ] Code coverage does not decrease below current threshold (80%)
- [ ] At least 1 reviewer approval
- [ ] PR description references ticket number
- [ ] No secrets or `.env.*` files in the diff

### 2.5 Merging `dev` → `main` (Production Release)

```bash
# On GitHub: open PR dev → main
# Review the full diff — this is a production release
# CI runs full test suite + integration tests against dev environment
# On approval: merge (squash merge preferred for clean main history)

# After merge, tag the release:
git checkout main
git pull origin main
git tag -a v1.2.0 -m "Release v1.2.0 — AIACC AIA tag support, update iterator"
git push origin v1.2.0
```

Production deployment is triggered automatically by merge to `main` (see Section 5).

---

## 3. Pre-Push Test Gates

### 3.1 Git Pre-Push Hook (Automatic Local Gate)

Install this hook once per developer:

```bash
# Run this once after cloning:
bash infrastructure/scripts/install-git-hooks.sh
```

File: `infrastructure/scripts/install-git-hooks.sh`

```bash
#!/bin/bash
cp infrastructure/git-hooks/pre-push .git/hooks/pre-push
chmod +x .git/hooks/pre-push
echo "Git hooks installed."
```

File: `infrastructure/git-hooks/pre-push`

```bash
#!/bin/bash
set -e

BRANCH=$(git rev-parse --abbrev-ref HEAD)
echo "🔍 Running pre-push checks for branch: $BRANCH"

# 1. Lint check
echo "→ Running linter..."
ruff check services/ lambdas/
ruff format --check services/ lambdas/
echo "✓ Lint passed"

# 2. Type check
echo "→ Running type checks..."
mypy services/orchestration --no-error-summary
echo "✓ Type checks passed"

# 3. Unit tests
echo "→ Running unit tests..."
pytest services/ lambdas/ -v --tb=short -q
echo "✓ Unit tests passed"

# 4. No secrets check (basic scan)
echo "→ Scanning for secrets..."
if git diff --cached --diff-filter=ACM | grep -E "(api_key|secret|password|token)\s*=\s*['\"][A-Za-z0-9]" --ignore-case; then
    echo "❌ Potential secret detected in diff. Remove it before pushing."
    exit 1
fi
echo "✓ No secrets detected"

echo ""
echo "✅ All pre-push checks passed. Pushing to $BRANCH..."
```

This hook runs automatically on every `git push`. If any check fails, the push is blocked and the developer sees the error locally before it ever reaches CI.

### 3.2 What the Pre-Push Hook Does NOT Do

The hook runs fast checks only. The following run in CI (not locally):
- Integration tests against real APIs
- Docker build verification
- E2E session flow tests
- Coverage threshold enforcement

---

## 4. CI/CD Pipeline — Dev Environment

### 4.1 GitHub Actions Workflow: PR to `dev`

File: `.github/workflows/ci-dev.yml`

```yaml
name: CI — Dev Branch

on:
  pull_request:
    branches: [dev]
  push:
    branches: [dev]

jobs:
  test:
    name: Unit Tests & Quality
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv and dependencies
        run: |
          pip install uv
          uv sync --all-packages

      - name: Lint
        run: |
          ruff check services/ lambdas/
          ruff format --check services/ lambdas/

      - name: Type check
        run: mypy services/orchestration

      - name: Unit tests with coverage
        run: |
          pytest services/ lambdas/ --cov=services --cov=lambdas \
            --cov-report=xml --cov-fail-under=80 -v

      - name: Upload coverage report
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  build-verify:
    name: Docker Build Verification
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4

      - name: Build all service images
        run: |
          docker build services/orchestration -t pmm-orchestration:ci

  deploy-dev:
    name: Deploy to Dev Environment
    runs-on: ubuntu-latest
    needs: [test, build-verify]
    if: github.ref == 'refs/heads/dev' && github.event_name == 'push'
    environment: dev
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.DEV_AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.DEV_AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Login to ECR
        run: |
          aws ecr get-login-password | docker login \
            --username AWS \
            --password-stdin ${{ secrets.DEV_ECR_REGISTRY }}

      - name: Build, tag and push images
        run: bash infrastructure/scripts/push-to-ecr.sh dev ${{ github.sha }}

      - name: Update ECS services
        run: |
          for service in pmm-orchestration; do
            aws ecs update-service \
              --cluster pmm-agent-dev \
              --service $service \
              --force-new-deployment \
              --region us-east-1
          done

      - name: Update Lambda functions
        run: |
          bash infrastructure/scripts/deploy-lambdas.sh dev

      - name: Upload context files to S3 dev
        run: |
          aws s3 sync context/ s3://egain-pmm-agent-context-dev/

      - name: Wait for ECS services to stabilise
        run: |
          for service in pmm-orchestration; do
            aws ecs wait services-stable \
              --cluster pmm-agent-dev \
              --services $service
          done
          echo "✅ All dev services stable"

      - name: Run post-deploy smoke tests (dev)
        run: |
          pytest tests/smoke/ \
            --base-url=${{ secrets.DEV_API_URL }} \
            --env=dev -v
        env:
          SMOKE_TEST_PM_EMAIL: ${{ secrets.DEV_SMOKE_TEST_PM_EMAIL }}

      - name: Deploy frontend to S3 dev
        run: |
          aws s3 sync frontend/ s3://egain-pmm-agent-ui-dev/ --delete
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.DEV_CF_DIST_ID }} \
            --paths "/*"

      - name: Notify Slack on failure
        if: failure()
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{ secrets.SLACK_DEPLOY_CHANNEL }}
          slack-message: "❌ PMM Agent dev deploy failed on commit ${{ github.sha }}"
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
```

### 4.2 Dev Environment Deployment Flow Summary

```
Developer pushes to feature/* branch
         │
         ▼
Opens PR: feature/* → dev
         │
         ▼
GitHub Actions: CI job runs
  ├── Lint ✓
  ├── Type check ✓
  ├── Unit tests + coverage ≥ 80% ✓
  └── Docker build verify ✓
         │
         ▼
PR approved by 1 reviewer
         │
         ▼
Merge to dev
         │
         ▼
GitHub Actions: deploy-dev job runs
  ├── Build + push images to ECR (dev)
  ├── Update ECS services (dev cluster)
  ├── Deploy Lambda functions (dev)
  ├── Sync context/ → S3 dev bucket
  ├── Wait for ECS services stable
  ├── Run smoke tests against dev URL  ← POST-DEPLOY GATE
  └── Deploy frontend to S3 dev + CloudFront invalidation
         │
    ┌────┴────┐
 [passes]   [fails]
    │           │
    ▼           ▼
  Done      Slack alert + 
            auto-rollback
            (see Section 6)
```

---

## 5. CI/CD Pipeline — Production Environment

### 5.1 GitHub Actions Workflow: Merge to `main`

File: `.github/workflows/deploy-prod.yml`

```yaml
name: Deploy — Production

on:
  push:
    branches: [main]

jobs:
  test-full:
    name: Full Test Suite
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install uv && uv sync --all-packages
      - name: Run full test suite
        run: pytest services/ lambdas/ --cov=services --cov=lambdas --cov-fail-under=80 -v

  integration-test-dev:
    name: Integration Tests Against Dev
    runs-on: ubuntu-latest
    needs: test-full
    steps:
      - uses: actions/checkout@v4
      - name: Run integration tests against dev environment
        run: |
          pytest tests/integration/ \
            --base-url=${{ secrets.DEV_API_URL }} \
            --env=dev -v -x
        env:
          TEST_PM_EMAIL: ${{ secrets.DEV_SMOKE_TEST_PM_EMAIL }}
          TEST_AHA_KEY: ${{ secrets.DEV_AHA_TEST_KEY }}

  deploy-prod:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [test-full, integration-test-dev]
    environment: production        # Requires manual approval in GitHub Environments
    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials (prod)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.PROD_AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.PROD_AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Login to ECR (prod)
        run: |
          aws ecr get-login-password | docker login \
            --username AWS \
            --password-stdin ${{ secrets.PROD_ECR_REGISTRY }}

      - name: Build, tag and push images (prod)
        run: bash infrastructure/scripts/push-to-ecr.sh prod ${{ github.sha }}

      - name: Blue/green deploy — update ECS services
        run: |
          for service in pmm-orchestration; do
            aws ecs update-service \
              --cluster pmm-agent-prod \
              --service $service \
              --force-new-deployment \
              --region us-east-1
          done

      - name: Deploy Lambda functions (prod)
        run: bash infrastructure/scripts/deploy-lambdas.sh prod

      - name: Sync context files to S3 prod
        run: aws s3 sync context/ s3://egain-pmm-agent-context-prod/

      - name: Wait for ECS services to stabilise (prod)
        run: |
          for service in pmm-orchestration; do
            aws ecs wait services-stable \
              --cluster pmm-agent-prod \
              --services $service \
              --region us-east-1
          done
          echo "✅ All prod services stable"

      - name: Run post-deploy smoke tests (prod)
        run: |
          pytest tests/smoke/ \
            --base-url=${{ secrets.PROD_API_URL }} \
            --env=prod -v
        env:
          SMOKE_TEST_PM_EMAIL: ${{ secrets.PROD_SMOKE_TEST_PM_EMAIL }}

      - name: Deploy frontend to S3 prod + CloudFront
        run: |
          aws s3 sync frontend/ s3://egain-pmm-agent-ui-prod/ --delete
          aws cloudfront create-invalidation \
            --distribution-id ${{ secrets.PROD_CF_DIST_ID }} \
            --paths "/*"

      - name: Tag release in GitHub
        run: |
          VERSION=$(cat VERSION)
          git tag -a "v$VERSION-prod" -m "Production deploy v$VERSION"
          git push origin "v$VERSION-prod"

      - name: Notify Slack on success
        uses: slackapi/slack-github-action@v1
        with:
          channel-id: ${{ secrets.SLACK_DEPLOY_CHANNEL }}
          slack-message: "✅ PMM Agent v${{ github.sha }} deployed to production"
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}

      - name: Notify Slack on failure and auto-rollback
        if: failure()
        run: |
          bash infrastructure/scripts/rollback-ecs.sh prod
        env:
          SLACK_BOT_TOKEN: ${{ secrets.SLACK_BOT_TOKEN }}
          SLACK_DEPLOY_CHANNEL: ${{ secrets.SLACK_DEPLOY_CHANNEL }}
```

### 5.2 Manual Approval Gate for Production

In GitHub repository Settings → Environments → `production`:
- Enable **Required reviewers**: add Tech Lead GitHub username
- Set **Wait timer**: 0 minutes (no auto-deploy delay)
- Result: every prod deploy pauses and requires a human to click **Approve** in the GitHub Actions UI before containers are pushed and services are updated

### 5.3 Production Deployment Flow Summary

```
Merge feature PRs into dev (tested + stable)
         │
         ▼
Open PR: dev → main
CI runs:
  ├── Full unit test suite ✓
  └── Integration tests against dev environment ✓
         │
         ▼
Tech Lead reviews + approves PR
         │
         ▼
Merge to main
         │
         ▼
GitHub Actions pauses at "production" environment gate
         │
         ▼
Tech Lead clicks "Approve deployment" in GitHub Actions UI
         │
         ▼
Deploy to prod ECS + Lambda + S3
         │
         ▼
Wait for ECS stable
         │
         ▼
Smoke tests run against prod URL  ← POST-DEPLOY GATE
         │
    ┌────┴────┐
 [passes]   [fails]
    │           │
    ▼           ▼
  Tag release  Auto-rollback ECS to previous task definition
  Slack notify Slack alert: "❌ Prod deploy failed — auto-rollback triggered"
```

---

## 6. Post-Deploy Smoke Tests

### 6.1 Smoke Test Suite

File: `tests/smoke/test_smoke.py`

These tests run against a live environment (dev or prod) after every deploy. They are fast (<60s total) and test only the critical path without affecting real data.

```python
import pytest
import httpx

@pytest.fixture
def client(base_url):
    return httpx.Client(base_url=base_url, timeout=30)

def test_health_orchestration(client):
    """All services are reachable and healthy."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"

def test_session_start(client, smoke_test_pm_email):
    """Session can be created and returns a session_id."""
    r = client.post("/sessions/start", json={
        "pm_email": smoke_test_pm_email,
        "mode": "release"
    })
    assert r.status_code == 200
    data = r.json()
    assert "session_id" in data
    assert data["awaiting_input"] is True
    assert len(data["message"]) > 0

def test_session_context_load(client, smoke_test_pm_email):
    """Company context loads correctly — PM products are returned."""
    r = client.post("/sessions/start", json={
        "pm_email": smoke_test_pm_email,
        "mode": "release"
    })
    session_id = r.json()["session_id"]
    status = client.get(f"/sessions/{session_id}/status")
    assert status.json()["pm_context"]["owned_products"] is not None

def test_tools_list_reachable(client):
    """Tool registry loaded — all 12 tools (6 Aha + 6 eGain) registered."""
    r = client.get("/internal/tools/list")
    assert r.status_code == 200
    tools = r.json()["tools"]
    assert len(tools) == 12, f"Expected 12 tools, got {len(tools)}: {tools}"

def test_context_invalidate_reachable(client):
    """Context invalidation endpoint responds."""
    r = client.post("/internal/context/invalidate", json={"key": "test"})
    assert r.status_code == 200

def test_session_cleanup(client, smoke_test_pm_email):
    """Sessions can be deleted."""
    r = client.post("/sessions/start", json={
        "pm_email": smoke_test_pm_email,
        "mode": "adhoc"
    })
    session_id = r.json()["session_id"]
    delete_r = client.delete(f"/sessions/{session_id}")
    assert delete_r.status_code == 200
```

### 6.2 Smoke Test Failure → Auto-Rollback

File: `infrastructure/scripts/rollback-ecs.sh`

```bash
#!/bin/bash
ENV=$1  # "dev" or "prod"
CLUSTER="pmm-agent-$ENV"

echo "🔄 Rolling back ECS services in $CLUSTER..."

for service in pmm-orchestration; do
    # Get the previous task definition revision
    CURRENT_TASK=$(aws ecs describe-services \
        --cluster $CLUSTER \
        --services $service \
        --query 'services[0].taskDefinition' \
        --output text)

    # Extract family and current revision number
    FAMILY=$(echo $CURRENT_TASK | cut -d':' -f6 | sed 's/:[0-9]*$//')
    CURRENT_REV=$(echo $CURRENT_TASK | rev | cut -d':' -f1 | rev)
    PREVIOUS_REV=$((CURRENT_REV - 1))

    echo "  Rolling back $service from rev $CURRENT_REV to $PREVIOUS_REV"
    aws ecs update-service \
        --cluster $CLUSTER \
        --service $service \
        --task-definition "$FAMILY:$PREVIOUS_REV" \
        --region us-east-1
done

echo "✅ Rollback initiated. Waiting for services to stabilise..."
for service in pmm-orchestration; do
    aws ecs wait services-stable --cluster $CLUSTER --services $service
done
echo "✅ Rollback complete."
```

---

## 7. Bug Triage & Hotfix Flow

### 7.1 Bug Found in Production — Standard Flow

For non-critical bugs (doesn't block all users):

```
1. PM or developer reports bug
2. Create GitHub Issue with label: bug, env:prod, priority:[P1/P2/P3]
3. Create fix branch from dev:
   git checkout dev && git pull origin dev
   git checkout -b fix/TICKET-456-aia-tag-parse-error
4. Write fix + regression test that would have caught the bug
5. Run local test gate: make test
6. PR: fix/* → dev
7. CI runs, deploy to dev, smoke tests pass
8. Verify fix in dev environment
9. PR: dev → main (standard prod deploy flow)
```

### 7.2 Critical Hotfix — Bypass `dev` Flow

For critical bugs (service down, all users blocked):

```bash
# Branch from main directly (NOT from dev)
git checkout main && git pull origin main
git checkout -b hotfix/TICKET-457-session-crash-on-start

# Fix and test
make test  # mandatory even for hotfixes

# PR: hotfix/* → main
# CI runs full test suite
# Tech Lead approves + merges immediately
# Smoke tests run post-deploy

# IMPORTANT: Also merge hotfix back to dev
git checkout dev
git merge hotfix/TICKET-457-session-crash-on-start
git push origin dev
```

### 7.3 Bug Tracking in Context Files

If a production bug reveals that `company-context.md` or a skill MD is incorrect (e.g., wrong Aha field name, wrong folder ID):

```bash
# These are content-only fixes, not code fixes
# Edit the relevant file in context/
# Create PR to dev with type: docs
# Once merged to dev: make upload-context-dev
# Once merged to main: make upload-context-prod
# No ECS redeployment needed — services reload context at session start
```

---

## 8. Frontend (S3 + CloudFront) Deployment

### 8.1 Frontend S3 Bucket + CloudFront Setup

Provisioned via Terraform (`infrastructure/terraform/modules/s3/main.tf`):

```hcl
# S3 bucket for frontend (static website hosting)
resource "aws_s3_bucket" "frontend" {
  bucket = "egain-pmm-agent-ui-${var.env}"
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id
  index_document { suffix = "index.html" }
  error_document  { key    = "index.html" }
}

# CloudFront distribution
resource "aws_cloudfront_distribution" "frontend" {
  origin {
    domain_name = aws_s3_bucket.frontend.bucket_regional_domain_name
    origin_id   = "S3-pmm-agent-ui-${var.env}"
  }
  enabled             = true
  default_root_object = "index.html"
  
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-pmm-agent-ui-${var.env}"
    viewer_protocol_policy = "redirect-to-https"
  }
  
  # Custom domain (optional)
  # aliases = ["pmm-agent.egain.com"]
  
  restrictions {
    geo_restriction { restriction_type = "none" }
  }
  
  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
```

### 8.2 Frontend File Structure

```
frontend/
├── index.html          # Main chat widget page (single file)
├── design-tokens.js    # eGain Prism design tokens (JS module)
└── assets/
    ├── egain-logo.svg
    └── favicon.ico
```

### 8.3 Frontend Deploy Commands

```bash
# Dev
make deploy-frontend-dev

# Prod
make deploy-frontend-prod
```

Both commands sync the `frontend/` folder to the appropriate S3 bucket and create a CloudFront cache invalidation so users get the latest version immediately.

### 8.4 CORS Configuration for API

The orchestration FastAPI service must allow requests from the CloudFront domain:

```python
# services/orchestration/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_ORIGIN_DEV", "https://dev.pmm-agent.egain.com"),
        os.getenv("FRONTEND_ORIGIN_PROD", "https://pmm-agent.egain.com"),
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
```

---

## 9. Environment Configuration Reference

### 9.1 GitHub Secrets Required

| Secret Name | Used In | Value |
|---|---|---|
| `DEV_AWS_ACCESS_KEY_ID` | ci-dev.yml | IAM key for dev account |
| `DEV_AWS_SECRET_ACCESS_KEY` | ci-dev.yml | IAM secret for dev account |
| `DEV_ECR_REGISTRY` | ci-dev.yml | `{account_id}.dkr.ecr.us-east-1.amazonaws.com` |
| `DEV_API_URL` | smoke tests | `https://dev-alb.pmm-agent.internal` or public ALB DNS |
| `DEV_CF_DIST_ID` | frontend deploy | CloudFront distribution ID (dev) |
| `DEV_SMOKE_TEST_PM_EMAIL` | smoke tests | A real dev-account PM email |
| `PROD_AWS_ACCESS_KEY_ID` | deploy-prod.yml | IAM key for prod account |
| `PROD_AWS_SECRET_ACCESS_KEY` | deploy-prod.yml | IAM secret for prod account |
| `PROD_ECR_REGISTRY` | deploy-prod.yml | Prod ECR registry |
| `PROD_API_URL` | smoke tests | Prod ALB URL |
| `PROD_CF_DIST_ID` | frontend deploy | CloudFront distribution ID (prod) |
| `PROD_SMOKE_TEST_PM_EMAIL` | smoke tests | Prod test PM email |
| `SLACK_BOT_TOKEN` | notifications | Slack bot token |
| `SLACK_DEPLOY_CHANNEL` | notifications | `#pmm-agent-deploys` or similar |

### 9.2 Environment Summary

| Aspect | Local | Dev | Prod |
|---|---|---|---|
| Redis | Docker (localhost:6379) | ElastiCache (private VPC) | ElastiCache (private VPC) |
| Secrets | `.env.local` override | AWS Secrets Manager | AWS Secrets Manager |
| Context bucket | N/A — local file path | `egain-pmm-agent-context-dev` | `egain-pmm-agent-context-prod` |
| Frontend | N/A | CloudFront dev distribution | CloudFront prod distribution |
| API URL | localhost:8000 | Dev ALB DNS | Prod ALB DNS |
| LLM provider | gemini (gemini-3-flash-preview) | gemini (gemini-3-flash-preview) | gemini (gemini-3-flash-preview) |
| Log level | debug | info | warn |
| ECS task count | N/A | 1 per service | 2 per service (HA) |

---

*Owner: Sai / eGain Platform Engineering*  
*Last updated: March 2026*
