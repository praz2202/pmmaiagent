# PMM AI Agent — Reference Guide

**Project:** eGain Product Marketing Manager (PMM) AI Agent
**Architecture:** Single PydanticAI Agent with tools, FastAPI backend, Redis session store
**Stack:** Python 3.11, FastAPI, PydanticAI, httpx, Redis, Logfire, Google Gemini
**Deployment:** Docker Compose on EC2, Nginx + Let's Encrypt

---

## 1 — Architecture Overview

The agent is a single PydanticAI `Agent` instance with tool functions registered on it. There is no graph, no node dispatch, no HITL gates. The agent receives a user message, decides which tools to call, and streams a response back via SSE.

```
User (browser) → GitHub Pages (MSAL login) → FastAPI (SSE) → PydanticAI Agent → Tools
                                                                                   ├─ aha_api_call (httpx)
                                                                                   ├─ egain_api_call (httpx)
                                                                                   ├─ load_skill
                                                                                   └─ (other tools)
```

**Key design decisions:**
- Direct httpx calls to Aha! and eGain APIs — no Lambda intermediary for API access
- Redis for session message history (with `ModelMessagesTypeAdapter` serialization)
- DynamoDB write at session end for long-term storage
- Context compaction to manage the model's context window
- Skills loaded on demand from `config/skills/` via `load_skill` tool
- System prompt is minimal (`prompts/system.txt`) with a skill index; detail lives in skill folders
- Google Gemini via `GoogleModel` (native API, not OpenAI-compatible)

---

## 2 — Repository Structure

```
pmm-ai-agent/
├── services/orchestration/          # Backend service
│   ├── main.py                      # FastAPI app, Logfire setup, SSE streaming
│   ├── agent.py                     # PydanticAI Agent definition, all tools, load_skill
│   ├── settings.py                  # Provider config, compaction settings
│   ├── compaction.py                # Context window management
│   ├── tools/
│   │   ├── api_client.py            # aha_api_call, egain_api_call (httpx)
│   │   └── deps.py                  # AgentDeps dataclass (lazy LambdaClient, GoogleModel)
│   ├── session/
│   │   ├── redis_client.py          # Redis connection, ModelMessagesTypeAdapter
│   │   └── session_history.py       # DynamoDB write at session end
│   └── context_loader/
│       ├── s3_loader.py             # Load context from S3
│       ├── skill_loader.py          # Load skill configs from config/skills/
│       └── prompt_loader.py         # Load prompts from prompts/ folder
├── config/skills/                   # Skill definitions (6 folders)
│   ├── release_features/
│   ├── feature_search/
│   ├── release_notes/
│   ├── portal_articles/
│   ├── context/
│   └── company_context/
├── prompts/
│   └── system.txt                   # Minimal system prompt with skill index
├── context/
│   └── company-context.md           # PM ownership, Aha mappings, portal context
├── frontend/
│   └── index.html                   # Chat widget with MSAL authentication
├── infrastructure/ec2/
│   ├── docker-compose.prod.yml      # Production compose (orchestration + Redis)
│   └── setup.sh                     # EC2 bootstrap script
├── .env.local                       # Local dev environment variables
├── .env.prod.example                # Production env template
├── Dockerfile                       # Container image for orchestration service
└── requirements.txt                 # Python dependencies
```

---

## 3 — Local Development Setup

### 3.1 — Prerequisites

- Python 3.11
- Docker and Docker Compose
- Redis (local install or via Docker)
- Access credentials for: Aha! API, eGain API, Google AI (Gemini), Azure AD (MSAL), AWS (S3/DynamoDB)

### 3.2 — Environment variables

Copy `.env.prod.example` to `.env.local` and fill in the values:

```bash
cp .env.prod.example .env.local
# Edit .env.local with your credentials
```

Key variables you need:

| Variable | Purpose |
|---|---|
| `GOOGLE_API_KEY` | Gemini model access |
| `AHA_API_KEY` | Aha! API token |
| `EGAIN_API_KEY` | eGain API token |
| `REDIS_URL` | Redis connection (default: `redis://localhost:6379`) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | S3 context files, DynamoDB sessions |
| `AZURE_CLIENT_ID` / `AZURE_TENANT_ID` | MSAL authentication |
| `LOGFIRE_TOKEN` | Logfire observability (optional for local) |
| `ENVIRONMENT` | `local` or `prod` (controls Logfire tags) |

### 3.3 — Install dependencies

```bash
cd services/orchestration
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.4 — Start Redis

Either run Redis locally:

```bash
redis-server
```

Or use Docker:

```bash
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### 3.5 — Run the service

```bash
cd services/orchestration
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Health check: `GET /`.

### 3.6 — Test with curl

```bash
# SSE streaming endpoint
curl -N http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What features are in the next release?", "session_id": "test-123"}'
```

---

## 4 — Key Code Walkthrough

### 4.1 — Agent (`agent.py`)

The single `Agent` instance is created with `GoogleModel` (Gemini). All tools are registered as functions on this agent. The `load_skill` tool dynamically loads skill context from `config/skills/` when the agent needs domain-specific instructions.

The agent uses `AgentDeps` (from `tools/deps.py`) as its dependency injection container, giving tools access to API clients, the model, and configuration.

### 4.2 — API Client (`tools/api_client.py`)

Two main functions:
- `aha_api_call` — makes authenticated httpx requests to the Aha! API
- `egain_api_call` — makes authenticated httpx requests to the eGain API

These are direct HTTP calls. No Lambda layer, no SDK wrapper.

### 4.3 — FastAPI App (`main.py`)

- Logfire integration with environment tags (`local`/`prod`)
- SSE streaming endpoint for chat
- Session management via Redis
- CORS configured for the GitHub Pages frontend

### 4.4 — Session Management

- **Active sessions:** Redis, using PydanticAI's `ModelMessagesTypeAdapter` for serialization (`session/redis_client.py`)
- **Completed sessions:** Written to DynamoDB at session end (`session/session_history.py`), including conversation messages for replay
- **Conversation history:** Frontend sidebar shows last 15 sessions per PM, queried via DynamoDB GSI on `pm_email + start_time`
- **Session replay:** Past conversations viewable read-only; active session shown with green ACTIVE badge

### 4.5 — Context Compaction (`compaction.py`)

When the conversation history grows too large for the model's context window, the compaction module summarizes older messages to free up space. Thresholds are configured in `settings.py`.

### 4.6 — Skills System

Skills live in `config/skills/` (6 folders). Each skill contains instructions and context for a specific domain task. The agent's system prompt (`prompts/system.txt`) contains a skill index so it knows what's available. When the agent calls `load_skill`, the skill loader reads the relevant folder and injects the instructions into the conversation context.

Current skills: `release_features`, `feature_search`, `release_notes`, `portal_articles`, `context`, `company_context`.

---

## 5 — Deployment

### 5.1 — Infrastructure

| Component | Detail |
|---|---|
| EC2 instance | t3.small, Ubuntu 22.04 |
| Key pair | `pmegain` |
| Security group | `sg-0b83b4cd5ad84afba` |
| Containers | Docker Compose: orchestration + Redis |
| Reverse proxy | Nginx on the host |
| TLS | Let's Encrypt for `api.controlflows.com` |
| Frontend hosting | GitHub Pages at `dev.controlflows.com` |

### 5.2 — Production URLs

- **Backend API:** https://api.controlflows.com
- **Frontend:** https://dev.controlflows.com

### 5.3 — Deploy process

The deployment is manual: push to git, SSH to EC2, pull, rebuild.

```bash
# From your local machine
git push origin main

# SSH into EC2
ssh -i ~/.ssh/pmegain.pem ubuntu@<ec2-ip>

# On EC2
cd /home/ubuntu/pmm-ai-agent
git pull origin main
cd infrastructure/ec2
docker compose -f docker-compose.prod.yml up -d --build
```

### 5.4 — First-time EC2 setup

Run the bootstrap script on a fresh Ubuntu 22.04 instance:

```bash
scp -i ~/.ssh/pmegain.pem infrastructure/ec2/setup.sh ubuntu@<ec2-ip>:~/
ssh -i ~/.ssh/pmegain.pem ubuntu@<ec2-ip>
chmod +x setup.sh && ./setup.sh
```

This installs Docker, Docker Compose, Nginx, and Certbot.

### 5.5 — Nginx configuration

Nginx runs on the EC2 host (not in a container) and reverse-proxies to the orchestration container on port 8000. Let's Encrypt handles TLS for `api.controlflows.com`.

### 5.6 — Environment variables in production

Create `.env.prod` on the EC2 instance (never committed to git):

```bash
cp .env.prod.example .env.prod
# Fill in production credentials
```

The Docker Compose file references this env file.

---

## 6 — Observability

**Logfire** is the observability platform. It is initialized in `main.py` and tags all traces with the `ENVIRONMENT` variable (`local` or `prod`).

PydanticAI has built-in Logfire integration, so agent runs, tool calls, and model interactions are automatically traced.

Access the Logfire dashboard to view:
- Agent execution traces
- Tool call durations and results
- API call latency (Aha!, eGain)
- Error rates and stack traces

---

## 7 — Frontend

The frontend is a single-page chat widget (`frontend/index.html`) hosted on GitHub Pages at `dev.controlflows.com`.

- **Authentication:** MSAL (Microsoft Authentication Library) for Azure AD login
- **Communication:** SSE streaming from the FastAPI backend
- **Deployment:** Push to the `gh-pages` branch (or configured branch) and GitHub Pages serves it automatically

---

## 8 — Adding a New Skill

1. Create a new folder under `config/skills/` with your skill name
2. Add instruction files (markdown or text) inside the folder
3. Update the skill index in `prompts/system.txt` so the agent knows about it
4. The `load_skill` tool will automatically pick it up

---

## 9 — Adding a New API Tool

1. Add your API function in `services/orchestration/tools/api_client.py` (or a new file under `tools/`)
2. Register it as a tool on the agent in `services/orchestration/agent.py`
3. The agent will discover it via its tool list and call it when relevant

---

## 10 — Troubleshooting

| Symptom | Check |
|---|---|
| Agent not responding | Verify Redis is running, check Logfire for errors |
| API calls failing | Check API keys in `.env`, verify network access from EC2 |
| CORS errors in browser | Verify allowed origins in `main.py` match `dev.controlflows.com` |
| Context too long errors | Check compaction settings in `settings.py` |
| Docker build fails | Check `requirements.txt` for version conflicts |
| SSL certificate expired | Run `sudo certbot renew` on EC2 |
| Session not persisting | Check Redis connectivity and `REDIS_URL` |
