# PMM AI Agent — DevOps & Deployment Guide

**Project:** PMM AI Agent
**Version:** 2.0
**Last updated:** March 2026

---

## Table of Contents

1. [Local Development Setup](#1-local-development-setup)
2. [Production Deployment](#2-production-deployment)
3. [Deploy Process](#3-deploy-process)
4. [Environment Configuration](#4-environment-configuration)
5. [Git Workflow](#5-git-workflow)
6. [Monitoring & Logs](#6-monitoring--logs)
7. [DNS](#7-dns)
8. [Bug Fixes & Hotfixes](#8-bug-fixes--hotfixes)

---

## 1. Local Development Setup

### 1.1 First-Time Setup

```bash
git clone git@github.com:egain/pmm-ai-agent.git
cd pmm-ai-agent

# Create your local environment file from the template
cp .env.prod.example .env.local
# Edit .env.local — fill in your API keys
```

### 1.2 Environment Variables (.env.local)

```bash
GEMINI_API_KEY=...
AHA_API_KEY=...
EGAIN_CLIENT_ID=...
EGAIN_CLIENT_SECRET=...
LOGFIRE_TOKEN=...
# Plus any other keys as needed
```

### 1.3 Start Infrastructure

Start Redis and DynamoDB Local via Docker Compose:

```bash
docker-compose up -d
```

### 1.4 Run the Backend

```bash
cd services/orchestration
PYTHONPATH=. uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 1.5 Run the Frontend

Serve the `frontend/` directory on localhost:3000 using any static file server:

```bash
# Example using Python's built-in server
cd frontend
python -m http.server 3000
```

### 1.6 Running Tests Locally

```bash
# Lint
ruff check services/

# Unit tests
pytest services/ -v --tb=short
```

These same checks run automatically via the pre-push hook (see Section 5).

---

## 2. Production Deployment

### 2.1 Infrastructure

| Component | Details |
|---|---|
| Server | EC2 t3.small, Ubuntu 22.04, us-west-2 |
| IP | 44.252.42.38 |
| SSH key | `pmegain.pem` |
| Services | Docker Compose: `infrastructure/ec2/docker-compose.prod.yml` (orchestration + Redis) |
| Reverse proxy | Nginx on port 80/443 forwarding to port 8000 |
| HTTPS | Let's Encrypt for api.controlflows.com (auto-renewing via certbot) |
| Frontend | GitHub Pages at dev.controlflows.com (auto-deploys on push to main) |

### 2.2 Frontend Deployment

The frontend is hosted on GitHub Pages and deploys automatically when changes are pushed to `main` via the GitHub Actions workflow at `.github/workflows/deploy-frontend.yml`.

---

## 3. Deploy Process

### 3.1 Frontend (Automatic)

Push to `main` triggers the GitHub Actions workflow, which deploys the frontend to GitHub Pages at dev.controlflows.com.

```bash
git push origin main
```

### 3.2 Backend (Manual SSH)

```bash
# 1. SSH into the EC2 instance
ssh -i pmegain.pem ubuntu@44.252.42.38

# 2. Pull latest code
cd /home/ubuntu/pmmaiagent && git pull origin main

# 3. Rebuild and restart containers
cd infrastructure/ec2
sudo docker compose -f docker-compose.prod.yml up -d --build

# 4. If only config/context changes (no code changes):
sudo docker compose restart orchestration
```

---

## 4. Environment Configuration

### 4.1 Environment Files

| File | Location | Purpose |
|---|---|---|
| `.env.local` | Developer machine | Local dev (git-ignored) |
| `.env.prod` | EC2 only (`/home/ubuntu/pmmaiagent`) | Production secrets (git-ignored) |
| `.env.prod.example` | Repo (committed) | Template for creating `.env.prod` |

### 4.2 Environment Summary

| Aspect | Local | Production |
|---|---|---|
| Redis | Docker (localhost:6379) | Docker on EC2 (via docker-compose.prod.yml) |
| DynamoDB | DynamoDB Local (Docker) | DynamoDB Local (Docker) or AWS |
| Secrets | `.env.local` | `.env.prod` on EC2 |
| Backend URL | localhost:8000 | api.controlflows.com (Nginx reverse proxy) |
| Frontend | localhost:3000 | dev.controlflows.com (GitHub Pages) |
| HTTPS | No | Yes (Let's Encrypt) |
| Log level | debug | warn |

---

## 5. Git Workflow

### 5.1 Branch Model

Single `main` branch. All work happens on `main` or short-lived feature branches merged back into `main`.

### 5.2 Pre-Push Hook

A pre-push Git hook runs automatically on every `git push`:

1. **Ruff lint** -- checks code style and errors
2. **Unit tests** -- runs pytest

If either check fails, the push is blocked.

### 5.3 CI/CD

| Target | Method |
|---|---|
| Frontend | GitHub Actions (`.github/workflows/deploy-frontend.yml`) -- deploys to GitHub Pages on push to `main` |
| Backend | Manual SSH deploy to EC2 (no CI/CD pipeline) |

### 5.4 Commit Message Convention

Follow Conventional Commits:

```
<type>(<scope>): <short description>
```

| Type | When to use |
|---|---|
| `feat` | New feature or tool |
| `fix` | Bug fix |
| `test` | Adding or fixing tests |
| `chore` | Dependency updates, config, non-code changes |
| `docs` | Documentation updates |
| `refactor` | Code restructure, no behavior change |

---

## 6. Monitoring & Logs

### 6.1 Logfire

Dashboard: https://logfire-us.pydantic.dev/dsp2202/pmm-ai-agent

Environment tags distinguish `local` vs `prod` traces.

### 6.2 Docker Logs (Production)

```bash
# SSH into EC2 first
sudo docker logs ec2-orchestration-1
sudo docker logs ec2-orchestration-1 --follow
sudo docker logs ec2-orchestration-1 --tail 100
```

---

## 7. DNS

| Domain | Target | Provider |
|---|---|---|
| api.controlflows.com | 44.252.42.38 (A record) | GoDaddy |
| dev.controlflows.com | GitHub Pages (CNAME) | GoDaddy |

---

## 8. Bug Fixes & Hotfixes

### 8.1 Standard Bug Fix

1. Fix the code locally and write a regression test
2. Run lint + tests locally (pre-push hook will enforce this)
3. `git push origin main`
4. Frontend auto-deploys via GitHub Actions
5. SSH to EC2 and pull + rebuild for backend changes (see Section 3.2)

### 8.2 Config/Context-Only Changes

If the fix is only in context files or environment config (no code changes):

```bash
# SSH to EC2
ssh -i pmegain.pem ubuntu@44.252.42.38
cd /home/ubuntu/pmmaiagent && git pull origin main
cd infrastructure/ec2 && sudo docker compose restart orchestration
```

No full rebuild needed -- a container restart picks up the new config.

---

*Owner: Sai*
*Last updated: March 2026*
