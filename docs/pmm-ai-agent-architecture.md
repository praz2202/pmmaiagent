# PMM AI Agent — Architecture Document

**Project:** eGain Product Marketing Manager (PMM) AI Agent
**Version:** 4.0 — Single PydanticAI Agent with Dynamic Skill Loading
**Status:** Production
**Author:** Sai / eGain Platform Engineering
**Last updated:** March 2026
**Repo:** github.com/praz2202/pmmaiagent (public)

---

## 1. Overview

The PMM AI Agent is an internal tool that helps eGain Product Managers keep portal documentation in sync with product releases. PMs interact via a chat interface; the agent fetches release context from Aha, surveys existing portal articles in eGain Knowledge, and assists with documentation tasks. The agent is conversational — it uses tools to gather information and responds naturally based on PM requests.

---

## 2. Key Design Principles

| Principle | Detail |
|---|---|
| **Single PydanticAI Agent** | One `Agent[AgentDeps, str]` with all tools registered. No graph, no nodes, no custom dispatch. The agent decides which tools to call based on the conversation. |
| **Dynamic skill loading** | The system prompt contains only a skill index table with one-liner descriptions. Full skill instructions (SKILL.md) are loaded on demand via the `load_skill(skill_name)` tool, keeping the base prompt minimal. |
| **Direct API calls** | All external API calls go through `tools/api_client.py` using httpx directly. No Lambda functions, no intermediary services. |
| **Credentials never in prompts** | Auth flows through `AgentDeps` via `RunContext`. The LLM sees tool descriptions and return values only — never base URLs, API keys, or auth headers. |
| **Skill folders for extensibility** | Each integration lives in a self-contained `config/skills/{name}/` folder with a SKILL.md (LLM instructions) and optional tools.py (tool functions). Adding a new integration means adding a new skill folder. |

---

## 3. System Components

### 3.1 Orchestration Service

The only deployable service. Runs on an EC2 instance (t3.small, Ubuntu 22.04, us-west-2) via Docker Compose.

**Stack:** Python 3.11, FastAPI, PydanticAI (single Agent), GoogleModel (native Gemini API), httpx, Redis, DynamoDB

**Responsibilities:**
- HTTP session lifecycle (`POST /sessions/start`, `POST /sessions/{id}/respond`, `POST /sessions/{id}/end`)
- SSE streaming with `agent.iter()` and tool call heartbeats
- PM resolution (`GET /pm/resolve`) for MSAL login flow
- Health check (`GET /health`)

### 3.2 Agent (`services/orchestration/agent.py`)

A single PydanticAI agent handles all conversations:

```python
pmm_agent: Agent[AgentDeps, str]
```

**Tools registered:**
- `RELEASE_FEATURES_TOOLS` — list_releases, fetch_release_features, get_feature_detail
- `FEATURE_SEARCH_TOOLS` — search_features
- `PORTAL_ARTICLES_TOOLS` — get_child_topics, browse_portal_topic, read_portal_article
- `CONTEXT_TOOLS` — get_release_tracking, get_portal_structure, get_document_rules
- `load_skill` — dynamically loads a skill's SKILL.md into the conversation

**System prompt:** Built by `@pmm_agent.instructions` from `prompts/system.txt` with PM context injected. The prompt is minimal — PM identity, behavioral rules, and a skill index table. Full skill instructions are loaded on demand when the agent calls `load_skill(skill_name)`.

### 3.3 Skill Folders (`config/skills/`)

Self-contained folders, each bundling LLM instructions and optional tool definitions for one capability.

```
config/skills/
├── release_features/
│   ├── SKILL.md           ← LLM instructions for release feature workflows
│   └── tools.py           ← list_releases, fetch_release_features, get_feature_detail
├── feature_search/
│   ├── SKILL.md           ← LLM instructions for feature search
│   └── tools.py           ← search_features
├── release_notes/
│   └── SKILL.md           ← Knowledge skill (no tools), release notes guidance
├── portal_articles/
│   ├── SKILL.md           ← LLM instructions for portal browsing and article reading
│   └── tools.py           ← get_child_topics, browse_portal_topic, read_portal_article
├── context/
│   └── tools.py           ← get_release_tracking, get_portal_structure, get_document_rules
└── company_context/
    └── SKILL.md           ← Developer reference (not loaded by agent)
```

**Dynamic loading:** The agent's system prompt includes a one-liner for each skill. When the agent needs detailed instructions for a task, it calls `load_skill("portal_articles")` which returns the full SKILL.md content. This keeps the base context window small.

### 3.4 API Client (`tools/api_client.py`)

Direct httpx calls to external APIs. No Lambda, no intermediary service. Two functions:

| Function | Auth | Target |
|---|---|---|
| `aha_api_call()` | Bearer token (env var `AHA_API_KEY`) | Aha API (`egain.aha.io/api/v1`) |
| `egain_api_call()` | On-Behalf-Of OAuth token (cached per `egain_username`) | eGain Knowledge API v4 (`api.egain.cloud`) |

404 errors return a friendly error dict instead of crashing. eGain is read-only — no write APIs are available or used.

### 3.5 Session State (Redis)

Redis (Docker Compose sidecar) stores live session state. Two key types per session:

| Key | Contents | TTL |
|---|---|---|
| `session:{id}` | `PMAgentState` (serialized) | 24 hours |
| `session:{id}:msgs` | PydanticAI message history (via `ModelMessagesTypeAdapter`) | 24 hours |

Each session belongs to exactly one PM — no shared state across sessions. When the PM clicks Restart, the session ends and a new independent session begins.

### 3.6 Session History (DynamoDB)

Stores completed session records including conversation messages for replay. Written once when a session ends (`POST /sessions/{id}/end`).

**Table:** `pmm-agent-sessions`
**Partition key:** `session_id` (String)
**GSI:** `pm_email-start_time-index` (pm_email HASH, start_time RANGE) — queries recent sessions per PM

**What is stored:** session_id, pm_name, pm_email, start/end time, status, title (first user message), conversation messages (user + assistant pairs), tool call metadata.

**What is NOT stored:** Full tool responses, raw LLM prompts, API credentials, Bearer tokens.

**Conversation history sidebar:** The frontend shows the last 15 conversations in a slide-out sidebar. PMs can click on past conversations to view them read-only (input bar disabled and greyed out). The active conversation is shown at the top with a green ACTIVE badge — clicking it returns to the in-progress chat.

### 3.7 Context Window Management (`compaction.py`)

Release sessions with many articles can accumulate large message histories. Compaction prevents context window overflow.

**Budget:** 480,000 chars (~120,000 tokens). Configured in `config.py`.

**Strategy — runs between conversation turns:**

1. **Trigger check** — after each turn, checks if total chars exceed 90% of 480k (432k chars)
2. **LLM summarization** — all messages except the last turn are sent to the LLM for summarization. The summary preserves: PM identity, tool calls with results (to prevent re-fetching), and current task state.
3. **Permanent replacement** — message history is replaced with `[summary] + [last_turn]`. Summary occupies up to ~10% of context (~48k chars), leaving ~90% free for future turns.

### 3.8 FastAPI Endpoints (`main.py`)

| Endpoint | Method | Purpose |
|---|---|---|
| `/sessions/start` | POST | Creates session, runs first agent turn |
| `/sessions/{id}/respond` | POST | SSE streaming via `agent.iter()`, tool call heartbeats |
| `/sessions/{id}/end` | POST | Writes session to DynamoDB, cleans Redis |
| `/sessions/history` | GET | Last 15 sessions for a PM (by email) |
| `/sessions/{id}/messages` | GET | Conversation messages for a past session (replay) |
| `/pm/resolve` | GET | Resolves PM email/name/egain_username to PM profile |
| `/health` | GET | Health check |

---

## 4. AgentDeps

Runtime-only dependency container. Never serialized — reconstructed each turn.

```python
@dataclass
class AgentDeps:
    lambda_client:   ...              # lazy, unused currently
    llm_model:       GoogleModel      # native Gemini API (NOT OpenAI-compatible)
    model_settings:  dict
    pm_context:      PMContext         # typed struct from company context
    session_id:      str
```

---

## 5. LLM Configuration

**Provider:** GoogleModel (native Gemini API via PydanticAI's `GoogleModel` class). This is NOT an OpenAI-compatible endpoint — it uses the Gemini SDK natively.

**Default model:** `gemini-3-flash-preview`

**API key:** Read from env var `GEMINI_API_KEY`. Falls back to AWS Secrets Manager if env var is not set.

---

## 6. Infrastructure

```
Internet
    │
    ├──► dev.controlflows.com (GitHub Pages)
    │         Frontend: MSAL login + chat widget
    │
    └──► api.controlflows.com (44.252.42.38)
              Nginx (Let's Encrypt HTTPS, port 80/443)
                  │
                  ▼
              Docker Compose (port 8000)
              ┌─────────────────────────────┐
              │  Orchestration Service       │
              │  (FastAPI + PydanticAI)      │
              │                              │
              │  Redis (sidecar container)   │
              └──────────┬──────────────────-┘
                         │
              ┌──────────┼───────────┐
              │          │           │
          Aha API    eGain API    DynamoDB
       (egain.aha.io) (api.egain.cloud) (session history)
                     (read-only)
```

**Host:** EC2 t3.small, Ubuntu 22.04, us-west-2
**Deployment:** Docker Compose — orchestration service + Redis
**Reverse proxy:** Nginx on port 80/443, proxies to port 8000
**HTTPS:** Let's Encrypt certificate for api.controlflows.com

### Infrastructure Decisions

| Component | Choice | Reason |
|---|---|---|
| Compute | EC2 + Docker Compose | Simple single-instance deployment. No container orchestration overhead needed for current scale. |
| Session state (live) | Redis (Docker sidecar) | In-memory speed for frequent reads per turn. TTL auto-expiry. Simple key-value access. |
| Session history (audit) | DynamoDB | Write-once at session end. Simple key-value. Pay-per-request fits low volume. |
| API calls | Direct httpx | No intermediary needed. Two API integrations with simple auth patterns. |
| Frontend hosting | GitHub Pages | Free, simple, separate deploy lifecycle from backend. |
| HTTPS | Let's Encrypt + Nginx | Free certificates, automatic renewal, standard reverse proxy. |

---

## 7. Frontend

Hosted on GitHub Pages at **dev.controlflows.com**.

**Authentication:**
- **Production:** MSAL popup login (Microsoft SSO, client ID: `6f082c2d-7e52-4f24-80e5-ae8f04bf9e68`). After login, calls `GET /pm/resolve` to match the Microsoft account to a PM.
- **Local dev:** PM dropdown for quick selection.

**Features:**
- SSE streaming with tool call heartbeats (shows which skill/tool is being called)
- Conversation history sidebar (hamburger menu, last 15 sessions)
- Active session badge — click to return to in-progress conversation
- Past conversations viewable read-only (grey input bar)
- Auto-login on page reload if MSAL session exists (no login flash)
- Loading spinner while checking auth
- Access denied UI for unauthorized users
- New conversation button: ends current session (writes to DynamoDB), starts fresh

---

## 8. Auth

| System | Auth Method | Details |
|---|---|---|
| Aha API | Bearer token | Env var `AHA_API_KEY`. Dedicated service account key. |
| eGain Knowledge API | On-Behalf-Of OAuth | Tokens cached per `egain_username` in api_client.py. |
| Gemini LLM | API key | Env var `GEMINI_API_KEY`, falls back to Secrets Manager. |
| Frontend (prod) | MSAL | Microsoft SSO popup → `/pm/resolve` to match PM. |

---

## 9. Observability

**Logfire** (Pydantic Logfire) is instrumented across the stack:
- `instrument_fastapi` — request/response spans
- `instrument_httpx` — outbound API call spans
- `instrument_pydantic_ai` — agent runs, tool calls, LLM interactions

**Environment tag:** `local` vs `prod` for filtering in the Logfire dashboard.

**Per-turn spans** include: `session_id`, `pm_name`, `user_input`, `agent_output`.

---

## 10. PM and Product Reference

### PM Ownership

| PM | Email | Products |
|---|---|---|
| Prasanth Sai | psai@egain.com | AIA, ECAI |
| Aiushe Mishra | amishra@egain.com | AIA |
| Carlos Espana | cespana@egain.com | ECAI |
| Varsha Thalange | vthalange@egain.com | AIA, ECAI, ECKN, ECAD |
| Ankur Mehta | amehta@egain.com | ECKN |
| Peter Huang | phuang@egain.com | ECKN |
| Kevin Dohina | kdohina@egain.com | ECAD |

7 PMs total. Emails are the short form (e.g., `psai@egain.com`). Each PM also has an `egain_username` for eGain API auth matching.

### Aha Products

| Product | Code | Aha URL | Release Type |
|---|---|---|---|
| AI Agent | `AIA` | `egain.aha.io/products/AIA` | Version tags (`AIA x.x.x`) |
| AI Services | `ECAI` | `egain.aha.io/products/ECAI` | Standard (`YY.MM`) |
| Knowledge | `ECKN` | `egain.aha.io/products/ECKN` | Standard (`YY.MM`) |
| Advisor Desktop | `ECAD` | `egain.aha.io/products/ECAD` | Standard (`YY.MM`) |

---

## 11. Security Considerations

### 11.1 Credential Isolation

API credentials are stored in environment variables (with Secrets Manager fallback). They never appear in Redis, tool descriptions, system prompts, or logs. The LLM sees tool names and docstrings only — never auth details.

### 11.2 Tool Sandboxing

The agent can only call tool functions explicitly registered on the `pmm_agent` Agent instance. There is no shell access, no `exec()`, no `subprocess`. Tool functions only call `aha_api_call()` or `egain_api_call()` in `api_client.py`.

### 11.3 Portal Safety

**eGain read-only:** No write APIs are available or used. The agent reads portal structure and articles. When the agent produces content, it presents it to the PM in the chat — the PM manually applies it in the eGain portal.

**PM isolation:** Each PM operates in an independent session scoped by `session_id`. No shared state between sessions.

**PM identity verification:** The agent resolves PM-owned products from company context at session start. A PM only sees releases and articles relevant to their assigned products.

### 11.4 Environment Variable Protection

- `.env` files are in `.gitignore` — never committed
- Development-time protection: `.claude/hooks/security-validator.sh` blocks reading `.env` files or dumping env vars during development

---

## 12. Extension Roadmap

New integrations require only a new skill folder in `config/skills/` with a SKILL.md and optional tools.py. Register tools on the agent and add a one-liner to the skill index in the system prompt.

---

*Build guide: `docs/pmm-ai-agent-guide.md`*
*Repository map: `REPO.md`*
