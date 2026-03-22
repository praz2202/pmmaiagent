# PMM AI Agent — Architecture Document

**Project:** eGain Product Marketing Manager (PMM) AI Agent  
**Version:** 3.0 — PydanticAI Graph Native (BaseNode + Graph.iter)  
**Status:** Implementation Ready  
**Author:** Sai / eGain Platform Engineering  
**Last updated:** March 2026  
**Related:** `pmm-ai-agent-guide.md` · `pmm-ai-agent-architecture-diagrams.md` · `REPO.md`

---

## 1. Overview

The PMM AI Agent is an internal workflow tool that helps eGain Product Managers keep portal documentation in sync with product releases. PMs interact via a chat interface; the agent fetches release context from Aha, surveys existing portal articles, proposes a structured update/create plan, iterates article-by-article with the PM at HITL gates, and publishes all confirmed content as portal drafts.

The agent operates in two modes:

**Release-driven mode:** PM triggers a documentation cycle for an upcoming release. The agent pulls release specs from Aha, compares them to the current eGain portal, generates an update and create plan, and walks the PM through each article before publishing drafts.

**Ad-hoc mode:** PM wants to update or create a specific article outside of a release cycle. The agent either asks which article or suggests the best match from a portal search.

---

## 2. Key Design Principles

| Principle | Detail |
|---|---|
| **Native PydanticAI Graph (`pydantic_graph`)** | All nodes are `@dataclass` classes that subclass `BaseNode[PMAgentState, AgentDeps]`. The `run()` method contains the logic (LLM call or Python), and the return type annotation defines valid edges — type-checked at graph construction. No custom `dispatch()` function. `Graph.iter()` + `GraphRun.next()` handles HITL pause/resume natively. |
| **HITL gates are code-enforced** | Confirmation checkpoints are graph node transitions — the code decides when to pause, not the LLM. There are 6 HITL gates: release confirm, plan review, mode select, per-article confirm (×2 for updates and creates), and output review. |
| **One service, Lambdas for API calls** | The orchestration service handles graph dispatch, session state, and LLM calls. All external API calls (Aha, eGain) execute in dedicated Lambda functions invoked by the orchestration service. No persistent client objects in the ECS process. |
| **Skill folders, not S3-hosted skills** | API knowledge (decision rules, tool definitions, client code) lives in `config/skills/` folders in the repo, versioned with code. Only `company-context.md` goes to S3 — it changes independently of code (new PMs, new releases). |
| **Credentials never in prompts** | Auth flows through `AgentDeps` via `RunContext`. The LLM sees tool descriptions and return values only — never base URLs, API keys, or auth headers. |
| **Company context as typed config** | `company-context.md` is parsed once per session into a `PMContext` struct. The raw Markdown is never injected into prompts. Each node receives only the slice of context it actually needs. |
| **Config-driven auth via tools.py** | Each skill's `tools.py` defines an `API_CONFIG` dict constant (auth type, credentials_secret, base_url). Tool functions pass this constant to the generic `pmm-skill-client` Lambda, which reads it per invocation, fetches credentials from Secrets Manager, and authenticates. No auth logic in the orchestration service. |
| **Extensibility via skill folders** | Adding Mailchimp, Jira, or any other integration means creating one new `config/skills/{name}/` folder with a `tools.py` that defines tool functions and an `API_CONFIG` constant. No Lambda changes, no graph changes, no new ECS services. |

---

## 3. System Components

### 3.1 Orchestration Service

The only deployable service. Runs as a single ECS Fargate task (1 vCPU / 2 GB).

**Stack:** Python 3.11, FastAPI, PydanticAI Graph (OpenAI SDK via PydanticAI `OpenAIModel`), httpx, Redis, boto3 (Lambda invoke)
**Responsibilities:**
- HTTP session lifecycle (`POST /sessions/start`, `POST /sessions/{id}/respond`, `POST /sessions/{id}/end`)
- SSE heartbeat stream for long-running tool-agent nodes
- PydanticAI `Graph.iter()` — runs the graph, pausing at HITL nodes; state saved to Redis at each pause
- Loads and caches company context from S3
- Loads skill SKILL.md files from repo at startup
- Invokes the generic skill Lambda (`pmm-skill-client`) for all external API calls, passing `api_config` from each skill's `tools.py`

### 3.2 Skill Folders (`config/skills/`)

Three self-contained folders following the Anthropic skills standard. Each bundles everything the agent needs for one integration.

```
config/skills/
├── aha/
│   ├── SKILL.md           ← LLM instructions: AIA vs standard routing, call order, filtering rules
│   ├── tools.py           ← 6 Python tool functions + AHA_API_CONFIG constant
│   ├── scripts/
│   │   └── aha_client.py  ← Aha-specific helpers (path resolution, AIA tag detection)
│   └── references/
│       └── api.md         ← Aha field paths, rate limit rules, release name formats (lazy-loaded)
├── egain/
│   ├── SKILL.md           ← LLM instructions: how to use read APIs, suggest create vs update logic
│   ├── tools.py           ← 2 read-only Python tool functions + EGAIN_API_CONFIG constant
│   └── references/
│       └── api.md         ← eGain Knowledge API v4 reference, article structure, HTML format (lazy-loaded)
└── company-context/
    ├── SKILL.md           ← LLM instructions: PMContext fields, release type rules
    └── references/
        └── parsing.md     ← Markdown table format, field extraction patterns
```

**Why skills are in the repo, not S3:** Skills change when code changes — a new tool, updated business rules, a new product. `company-context.md` changes independently (a PM joins, a release date shifts). Keeping them separate means updating a PM's email doesn't require a deploy.

**One generic Lambda for all skills:** A single `pmm-skill-client` Lambda handles all external API calls for every skill. Each skill's `tools.py` defines an `API_CONFIG` Python dict constant containing the auth type, credentials secret, and base URL. Tool functions pass this constant to the Lambda as part of the invocation payload. The Lambda reads this config, resolves credentials from Secrets Manager, makes the API call, and returns the result. No persistent state is maintained — each invocation is independent. Adding a new skill (Jira, Mailchimp, etc.) requires zero Lambda changes — just a new `tools.py` with tool functions and the right `API_CONFIG` constant.

**eGain is read-only:** The eGain Knowledge API only exposes read endpoints (get articles in topic, get article by ID). There are no create or update APIs. When the agent produces content for a new or updated article, it presents the HTML content to the PM in the chat — the PM manually applies it in the eGain portal. The agent suggests whether to create a new article or update an existing one based on how closely the content matches existing portal articles.

### 3.3 Company Context (`context/company-context.md` → S3)

A Markdown file uploaded to S3 that the orchestration service loads and parses at session start into a typed `PMContext` struct. Contains:

- PM-to-product ownership (who owns AIA, ECAI, ECKN, ECAD)
- Aha product mappings (product code, release type, Aha URL)
- Release cadence rules (AIA uses version tags; ECAI/ECKN/ECAD use standard YY.MM releases)
- eGain portal context per product (portal ID, portal name, topic names → topic IDs)
- Upcoming releases

Cached for 5 minutes at the process level. A Lambda (`context-refresher`) fires on S3 `ObjectCreated` events and calls `POST /internal/context/invalidate` to drop the cache immediately when the file is updated.

### 3.4 Session State (ElastiCache Redis)

Stores `PMAgentState` per `session_id`. TTL: 24 hours.

One key type:
- `session:{session_id}` — full `PMAgentState` (no credentials, no raw context text)

Each session belongs to exactly one PM — there is no shared memory or state across sessions. A session is a single conversation thread: one PM, one release (or ad-hoc task), one `message_history`. When the PM clicks Restart, the session ends (written to DynamoDB) and a new independent session begins.

This allows HITL sessions to survive across multiple HTTP requests and browser refreshes. On each resumed turn the orchestration service rehydrates `AgentDeps` from the stored state.

### 3.5 Lambdas

Two Lambda functions:

| Lambda | Trigger | Purpose |
|---|---|---|
| `pmm-skill-client` | Invoked by orchestration service (`boto3 lambda.invoke`) | **Generic skill executor for all API integrations.** Receives `{method, path, params, api_config}`. Reads `api_config.auth` to determine auth strategy: `basic` → fetches credentials from Secrets Manager and builds auth header. Creates a fresh httpx client, makes the API call, returns the result. Stateless per invocation. |
| `pmm-context-refresher` | S3 `ObjectCreated` event on context bucket | Calls `POST /internal/context/invalidate` on the orchestration service to drop the company-context cache immediately. |

Both Lambdas are stateless and short-lived. `pmm-skill-client` does not maintain connection pools or rate limiters — if an external API returns a rate limit error (429), the Lambda propagates the error and the agent surfaces it to the PM. Auth strategy is driven entirely by the `api_config` dict passed in each tool invocation payload (defined in each skill's `tools.py`) — adding a new skill requires no Lambda code changes.

**Supported auth types:**

| `api.auth.type` | Behaviour | Example skill |
|---|---|---|
| `basic` | Fetches `credentials_secret` from Secrets Manager, extracts `secret_field`, builds `Authorization: Basic` header | Aha |
| `basic_onbehalf` | Fetches `credentials_secret` from Secrets Manager (`client_app`, `client_secret`), builds on-behalf-of-customer auth header | eGain |

### 3.6 Secrets (AWS Secrets Manager)

| Secret | Contents |
|---|---|
| `pmm-agent/aha-api-key` | `{"api_key": "..."}` | Fetched by `pmm-skill-client` Lambda (declared in `aha/tools.py` `AHA_API_CONFIG`) |
| `pmm-agent/egain-credentials` | `{"client_app": "...", "client_secret": "..."}` | Fetched by `pmm-skill-client` Lambda (declared in `egain/tools.py` `EGAIN_API_CONFIG`). On-behalf-of-customer auth. |
| `pmm-agent/gemini-api-key` | `{"api_key": "..."}` | Fetched by orchestration service — default LLM provider |
| `pmm-agent/anthropic-api-key` | `{"api_key": "..."}` | Fetched by orchestration service — Anthropic LLM provider |
| `pmm-agent/openai-api-key` | `{"api_key": "..."}` | Fetched by orchestration service — OpenAI LLM provider |

The `pmm-skill-client` Lambda fetches skill credentials from Secrets Manager per invocation. The orchestration service fetches only the LLM API key for the active provider (configured via `DEFAULT_PROVIDER` in `config.py`). Never appear in any tool description or any Redis key. IAM roles scoped to `pmm-agent/*` only.

### 3.7 Session History (DynamoDB)

Stores completed session records for audit and history. Written once when a session ends (PM clicks restart, or the session reaches `DoneNode`).

**Table:** `pmm-agent-sessions`
**Partition key:** `session_id` (String)

```python
class SessionRecord(BaseModel):
    session_id:        str
    pm_name:           str
    pm_email:          str
    mode:              str                  # "release" | "adhoc"
    release_label:     str | None = None
    start_time:        str                  # ISO 8601
    end_time:          str                  # ISO 8601
    status:            str                  # "completed" | "restarted"
    tool_calls:        list[ToolCallRecord] = []
    node_transitions:  list[NodeTransition] = []

class ToolCallRecord(BaseModel):
    tool_name:  str
    params:     dict
    timestamp:  str
    result:     str = "tool response received"   # never store full response

class NodeTransition(BaseModel):
    node:       str
    timestamp:  str
```

**What is NOT stored:** Full tool responses, raw LLM prompts, API credentials, Bearer tokens. Only tool call names, parameters, and the fact that a response was received.

**Why DynamoDB:** Write-once at session end. Simple key-value access. No need for relational queries. Pay-per-request pricing fits the low write volume.

### 3.8 Frontend (S3 + CloudFront)

Single-file `index.html` chat widget with eGain Prism brand tokens. Connects to the orchestration service via REST + SSE. Deployed to S3 and served via CloudFront.

**PM selection dropdown:** Before a session starts, the widget shows a dropdown with four PMs: Prasanth, Aiushe, Carlos, Varsha. The selected PM name is sent with `POST /sessions/start` and determines which products, releases, and portal articles the agent works with.

**Restart button:** Ends the current session (writes the session record to DynamoDB), returns to the PM selection dropdown, and starts a fresh session. The PM can pick a different name on restart.

### 3.9 LLM Provider Configuration

Three LLM providers are configured in `config.py`. All use PydanticAI's `OpenAIModel` with provider-specific `base_url` — every provider exposes an OpenAI-compatible API.

```python
# config.py — LLM provider configuration
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
DEFAULT_MODEL_SETTINGS = {"extra_body": {"reasoning_effort": "low"}}
```

**Default provider:** Gemini (`gemini-3-flash-preview`). Change `DEFAULT_PROVIDER` in `config.py` to switch all agent nodes to a different provider — no code changes needed.

**Reasoning effort:** Set to `"low"` via `extra_body` in PydanticAI model settings. Passed to all providers — Anthropic ignores unsupported params.

**API keys:** In production, fetched from Secrets Manager (`credentials_secret`). Locally, set via env vars (`api_key_env`). The orchestration service resolves the key at startup and passes it to `OpenAIModel`.

### 3.10 Context Window Management (Compaction)

Release-flow sessions with many articles can accumulate large message histories (tool responses, article HTML, PM feedback across multiple iterations). Compaction prevents context window overflow.

**Budget:** 480,000 chars ≈ 120,000 tokens. Configured in `config.py` — all thresholds are constants, easy to adjust.

**Strategy — runs BETWEEN conversation turns, not mid-turn:**

1. **Tool response capping** — `cap_tool_response()` enforces a 60,000 char limit per tool response with a timestamp. Prevents one large Aha feature list from consuming the entire context.

2. **Trigger check** — after each turn, `maybe_compact(state, model)` checks if `state.total_chars > COMPACTION_TRIGGER_CHARS` (90% of 480k = 432k chars).

3. **LLM summarization** — all messages EXCEPT the last turn are serialized and sent to the LLM with `COMPACTION_PROMPT.txt`. The summary preserves: PM identity, tool calls with results (to prevent re-fetching), plan state, article confirmation status.

4. **Permanent replacement** — `state.message_history` is permanently replaced with `[summary] + [last_turn]`. The old messages are gone. The summary occupies up to ~10% of context (48k chars / 12k tokens), the last turn stays verbatim, leaving ~90% free for future turns.

**Post-compaction state:**
```
[summary ≤ 48k chars] + [last turn verbatim] = ~10% of context used
                                                ~90% free for more turns
```

**Key design decisions:**
- Summary max is 12,000 tokens (48k chars) — the LLM should be as concise as possible, 12k is the ceiling not a target
- Only the last turn is protected — everything else is summarized
- Compaction uses the same LLM provider (Gemini Flash) with `temperature=0.2`
- Tool call arguments and results are preserved verbatim in the summary to prevent duplicate API calls
- Old messages are permanently cleared — this is not reversible (DynamoDB session history has the audit trail)

---

## 4. PydanticAI Graph — 21 Nodes, 6 HITL Gates

All nodes are `@dataclass` classes that subclass `BaseNode[PMAgentState, AgentDeps]`. The `run()` method contains the node logic — either an LLM agent call or pure Python. The return type annotation defines valid outgoing edges, validated at graph construction. No custom `dispatch()` function — `pydantic_graph.Graph` handles routing natively.

```python
pmm_graph = Graph(nodes=[EntryNode, ContextSetupNode, ...], state_type=PMAgentState, deps_type=AgentDeps)
```

### 4.1 Release-Driven Flow

```
EntryNode [LLM reasoning]
    │ (release intent)
    ▼
ContextSetupNode [Python logic] ──────────────────────────────────────────────
    │                                                                         │
    ▼                                                                         │
ReleaseConfirmNode [LLM] ★ HITL #1                                           │
    │ PM picks release (AIA: version tags / ECAI·ECKN·ECAD: standard YY.MM)  │
    ▼                                                                         │
ReleaseContextAgentNode [Tool-Agent] ← Aha tools (1–3 API calls via Lambda)  │
    │                                                                         │
    ▼                                                                         │
PortalContextAgentNode [Tool-Agent] ← eGain tools (read-only, via Lambda)   │
    │                                                                         │
    ▼                                                                         │
PlanGenNode [LLM reasoning] ← if plan_feedback set, re-runs with feedback   │
    │                                                                         │
    ▼                                                                         │
PlanReviewNode [LLM] ★ HITL #2 ──(edit)──► PlanGenNode (loops w/ feedback)  │
    │ (confirm)                                                               │
    ▼                                                                         │
ModeSelectNode [Python logic] ★ HITL #3 (updates first or creates first?)    │
    │                                                                         │
    ├── UpdateIterator loop:                                                  │
    │     ShowUpdatePlan [Python fmt] → UpdateFeedback ★ HITL #4              │
    │       → RefineUpdate [LLM] / AdvanceUpdate [Python logic]               │
    │                                                                         │
    └── CreateIterator loop:                                                  │
          ShowCreatePlan [Python fmt] → CreateFeedback ★ HITL #5              │
            → RefineCreate [LLM] / AdvanceCreate [Python logic]               │
                                                                              │
                                            OutputAgentNode [LLM reasoning] ──┘
                                                    │  (presents HTML + create/update
                                                    │   recommendation to PM)
                                                    ▼
                                            OutputReviewNode [LLM] ★ HITL #6
                                              │ (approved)     │ (feedback)
                                              ▼                └──► OutputAgentNode
                                            DoneNode
```

### 4.2 Ad-Hoc Flow

```
EntryNode
    │ (specific article intent)
    ▼
AdHocRouterNode ★ HITL
    ├── (knows article) ──► AskArticleNode ──► ShowUpdatePlan or ShowCreatePlan
    └── (suggest me)   ──► SuggestNode ────► ShowUpdatePlan (confirmed)
                               └── (rejected) loops back to SuggestNode
```

### 4.3 Node Implementation Pattern

Every node — whether it uses an LLM or pure Python — follows the same `BaseNode` pattern:

```python
@dataclass
class PlanGenNode(BaseNode[PMAgentState, AgentDeps]):
    """LLM reasoning — generates documentation plan."""
    async def run(self, ctx: GraphRunContext[PMAgentState, AgentDeps]) -> PlanReviewNode:
        result = await plan_gen_agent.run(prompt, deps=ctx.deps, model=ctx.deps.llm_model, ...)
        ctx.state.plan = result.output.plan
        return PlanReviewNode()

@dataclass
class ModeSelectNode(BaseNode[PMAgentState, AgentDeps]):
    """Python logic — PM picks updates first or creates first."""
    async def run(self, ctx: GraphRunContext[PMAgentState, AgentDeps]) -> ShowUpdatePlanNode | ShowCreatePlanNode:
        text = (ctx.state.pm_input or "").lower()
        if "create" in text:
            return ShowCreatePlanNode()
        return ShowUpdatePlanNode()
```

- Return type = outgoing edges, validated at `Graph(nodes=[...])` construction
- State mutations via `ctx.state` (the `PMAgentState`)
- Dependencies via `ctx.deps` (the `AgentDeps` — LambdaClient, llm_model, skills, pm_context)
- No `dispatch()` function — `pydantic_graph.Graph` handles routing
- HITL: `Graph.iter()` pauses after each node. FastAPI checks if the next node needs PM input, saves state to Redis if so, and resumes on the next HTTP request via `GraphRun.next()`

### 4.4 Node Type Summary

| Node | Type | LLM | HITL | Notes |
|---|---|---|---|---|
| `EntryNode` | LLM reasoning | Yes | — | Routes to release or ad-hoc flow |
| `ContextSetupNode` | Python logic | No | — | Validates pm_context is loaded |
| `ReleaseConfirmNode` | LLM reasoning | Yes | #1 | PM picks release |
| `ReleaseContextAgentNode` | Tool-Agent | Yes | — | Aha tools (AHA_TOOLS) |
| `PortalContextAgentNode` | Tool-Agent | Yes | — | eGain tools (EGAIN_TOOLS) |
| `PlanGenNode` | LLM reasoning | Yes | — | Generates DocumentPlan |
| `PlanReviewNode` | LLM reasoning | Yes | #2 | PM reviews/edits plan |
| `ModeSelectNode` | Python logic | No | #3 | Keyword match on PM input |
| `ShowUpdatePlanNode` | Python formatting | No | — | Formats ArticlePlan for PM |
| `UpdateFeedbackNode` | LLM reasoning | Yes | #4 | Interprets PM confirm/feedback |
| `RefineUpdateNode` | LLM reasoning | Yes | — | Refines article content |
| `AdvanceUpdateNode` | Python logic | No | — | Iterator advance + routing |
| `ShowCreatePlanNode` | Python formatting | No | — | Formats new article plan |
| `CreateFeedbackNode` | LLM reasoning | Yes | #5 | Interprets PM confirm/feedback |
| `RefineCreateNode` | LLM reasoning | Yes | — | Refines new article content |
| `AdvanceCreateNode` | Python logic | No | — | Iterator advance + routing |
| `OutputAgentNode` | LLM reasoning | Yes | — | Generates HTML + recommendations |
| `OutputReviewNode` | LLM reasoning | Yes | #6 | PM approves or requests changes |
| `DoneNode` | Python logic | No | — | Returns `End[str]`, session complete |
| `AdHocRouterNode` | LLM reasoning | Yes | HITL | Routes ad-hoc intent |
| `SuggestNode` | Tool-Agent | Yes | — | Searches portal for best match |

**12 nodes use LLM, 7 use pure Python, 2 use tools.** Python-logic nodes can be upgraded to LLM agents later (e.g., when new capabilities make routing decisions more complex) without changing the graph structure — just change what happens inside `run()`.

### 4.5 HITL Gate Summary

| Gate | Node | Pauses on | Confirm routes to | Edit/reject routes to |
|---|---|---|---|---|
| 1 | `ReleaseConfirmNode` | Release list presented | `ReleaseContextAgentNode` | Back to gate (re-prompts) |
| 2 | `PlanReviewNode` | Full plan presented | `ModeSelectNode` | `PlanGenNode` (with feedback) |
| 3 | `ModeSelectNode` | Mode question | `ShowUpdatePlanNode` or `ShowCreatePlanNode` | Back to gate |
| 4 | `UpdateFeedbackNode` | Per-article update shown | `AdvanceUpdateNode` | `RefineUpdateNode` |
| 5 | `CreateFeedbackNode` | Per-article draft shown | `AdvanceCreateNode` | `RefineCreateNode` |
| 6 | `OutputReviewNode` | Final HTML output shown | `DoneNode` | `OutputAgentNode` (re-runs with feedback) |

---

## 5. Tool Registration and Auth

Each skill has a `tools.py` file that contains plain async Python functions and an `API_CONFIG` dict constant. Agent nodes import tools directly — no registry, no YAML parsing, no dynamic loader.

**Pattern:** Each tool function has typed parameters (Pydantic validates), a docstring (the LLM sees this as the tool description), and calls `ctx.deps.lambda_client.invoke_skill_lambda()` with the skill's `API_CONFIG` constant. Each skill exports a `*_TOOLS` list that agent nodes pass to `Agent(..., tools=...)`.

```python
# config/skills/aha/tools.py — one tool shown (6 total)

from pydantic_ai import RunContext
from services.orchestration.session.models import AgentDeps

AHA_API_CONFIG = {
    "auth": {"type": "basic", "credentials_secret": "pmm-agent/aha-api-key", "secret_field": "api_key"},
    "base_url": "https://egain.aha.io/api/v1",
}

async def aha_get_release_features(
    ctx: RunContext[AgentDeps],
    product_key: str,
    release_id: str,
    fields: str = "name,description,tags,custom_fields",
) -> dict:
    """Get all features for a release in an Aha product. Returns feature name, description, tags, and custom fields."""
    return await ctx.deps.lambda_client.invoke_skill_lambda(
        lambda_name="pmm-skill-client",
        payload={
            "method": "GET",
            "path": f"/products/{product_key}/releases/{release_id}/features",
            "params": {"fields": fields},
            "api_config": AHA_API_CONFIG,
        },
    )

# ... 5 more tool functions ...

AHA_TOOLS = [
    aha_get_release_features,
    aha_get_releases,
    aha_get_feature_by_id,
    aha_get_features_by_tag,
    aha_search_features,
    aha_get_feature_tasks,
]
```

```python
# config/skills/egain/tools.py — both tools shown (2 total, read-only)

from pydantic_ai import RunContext
from services.orchestration.session.models import AgentDeps

EGAIN_API_CONFIG = {
    "auth": {"type": "basic_onbehalf", "credentials_secret": "pmm-agent/egain-credentials"},
    "base_url": "https://apidev.egain.com/knowledge/v4",
}

async def egain_get_articles_in_topic(
    ctx: RunContext[AgentDeps],
    topic_id: str,
    limit: int = 100,
) -> dict:
    """Get all articles in an eGain Knowledge portal topic. Returns article titles, IDs, and summaries."""
    return await ctx.deps.lambda_client.invoke_skill_lambda(
        lambda_name="pmm-skill-client",
        payload={
            "method": "GET",
            "path": f"/topics/{topic_id}/articles",
            "params": {"limit": limit},
            "api_config": EGAIN_API_CONFIG,
        },
    )

async def egain_get_article_by_id(
    ctx: RunContext[AgentDeps],
    article_id: str,
) -> dict:
    """Get a single eGain Knowledge article by ID. Returns full article content including HTML body."""
    return await ctx.deps.lambda_client.invoke_skill_lambda(
        lambda_name="pmm-skill-client",
        payload={
            "method": "GET",
            "path": f"/articles/{article_id}",
            "params": {},
            "api_config": EGAIN_API_CONFIG,
        },
    )

EGAIN_TOOLS = [egain_get_articles_in_topic, egain_get_article_by_id]
```

**Agent nodes import tools directly and use `BaseNode`:**

```python
# graph/nodes/release_context_agent.py — BaseNode with tool-agent
from config.skills.aha.tools import AHA_TOOLS

release_context_agent = Agent(deps_type=AgentDeps, result_type=ReleaseContextResult, tools=AHA_TOOLS)

@dataclass
class ReleaseContextAgentNode(BaseNode[PMAgentState, AgentDeps]):
    """Tool-Agent — fetches release features from Aha."""
    async def run(self, ctx: GraphRunContext[PMAgentState, AgentDeps]) -> PortalContextAgentNode:
        result = await release_context_agent.run(prompt, deps=ctx.deps, model=ctx.deps.llm_model, ...)
        ctx.state.aha_specs = result.output.features
        return PortalContextAgentNode()
```

The LLM sees tool names and docstrings only. Each tool call invokes the single `pmm-skill-client` Lambda via `boto3 lambda.invoke`, passing the `API_CONFIG` constant from the skill's `tools.py`. The Lambda reads auth config from the payload, fetches credentials from Secrets Manager, and makes the API call. Credentials never appear in any prompt or in the orchestration service.

**eGain read-only:** The eGain skill only has read tools (`egain_get_articles_in_topic`, `egain_get_article_by_id`). There are no write operations. When the agent produces article content, it presents the HTML to the PM in the chat with a recommendation to create a new article or update an existing one (or both options if ambiguous).

---

## 6. Concurrency Model

Multiple PMs can use the service simultaneously. Resources are split into two scopes:

### Process-level (shared across all sessions)

| Resource | Rationale |
|---|---|
| Company context parse cache (5-min TTL) | Parsing the same Markdown on every session start is wasteful. All sessions share one parse result. |
| Skill SKILL.md strings (lru_cache) | Skills change only on deploy. Load once, cache indefinitely. |
| `LambdaClient` (boto3 Lambda client) | Shared boto3 client for invoking skill Lambdas. Stateless — just a thin invocation wrapper. |

### Per-session (isolated in Redis)

| Resource | Rationale |
|---|---|
| `PMAgentState` | Each session has its own release, plan, iterator state, and PM input. The `session_id` in `PMAgentState` provides session isolation for all external API calls (e.g., eGain uses read-only `basic_onbehalf` auth scoped by `session_id`). |

### Lambda-level (no shared state)

| Resource | Rationale |
|---|---|
| `pmm-skill-client` Lambda | Single generic Lambda for all skills. Each invocation reads `api_config` from the payload to determine auth strategy. Creates a fresh httpx client, authenticates, makes the API call, and exits. No connection pool, no rate limiter. If an API returns 429, the error propagates to the agent. |

`AgentDeps` is reconstructed each HTTP turn from the stored state and passed to `Graph.iter(deps=agent_deps)`. Each node accesses it via `ctx.deps`. It is never serialised to Redis.

**Graph execution per HTTP request:** Each FastAPI endpoint (`/sessions/start`, `/sessions/{id}/respond`) creates a `Graph.iter()` context and steps through nodes with `GraphRun.next()`. When the next node is a HITL gate, the graph pauses — state is saved to Redis — and the HTTP response is returned. The PM's next message resumes the graph from the saved node.

---

## 7. Data Models

All models in `services/orchestration/session/models.py`.

### `PMContext`
Parsed from `company-context.md` at session start. Never stored raw — always a typed struct.

```python
class PMContext(BaseModel):
    pm_id:                 str
    name:                  str
    owned_products:        list[str]          # ["AIA", "ECAI"]
    aha_mappings:          dict[str, AhaMapping]
    portal_folders:        dict[str, str]     # topic name → folder_id
    release_cadence_rules: str
    upcoming_releases:     list[dict]
```

### `AhaMapping`
Per-product Aha configuration.

```python
class AhaMapping(BaseModel):
    product:            str
    aha_product_key:    str               # "AIA", "ECAI", "ECKN", "ECAD"
    release_field_type: str               # "aia_version_tag" | "standard_release"
    aia_version_prefix: str | None = None # "AIA" for AIA, None otherwise
    shipped_tag:        str | None = None
```

### `ArticlePlan`
One article update or create, with PM-facing fields and working content.

```python
class ArticlePlan(BaseModel):
    title:           str
    article_id:      str | None = None    # None for creates
    folder_id:       str | None = None    # None for updates
    planned_changes: str                  # shown to PM
    refined_content: str | None = None   # live working content through feedback
    jira_url:        str | None = None
    confirmed:       bool = False
```

### `IteratorState`
Per-article loop tracking for updates and creates.

```python
class IteratorState(BaseModel):
    articles:           list[ArticlePlan] = []
    current_index:      int = 0
    confirmed_articles: list[ArticlePlan] = []

    def is_done(self) -> bool:
        return self.current_index >= len(self.articles)
```

### `PMAgentState`
The Redis-serialised session. Contains no credentials, no raw context text, no live client objects.

```python
class PMAgentState(BaseModel):
    session_id:            str
    pm_name:               str                   # from frontend dropdown
    pm_context:            PMContext | None = None
    release_id:            str | None = None
    release_label:         str | None = None
    aha_specs:             list[dict] | None = None
    portal_articles:       list[dict] | None = None
    plan:                  DocumentPlan | None = None
    plan_feedback:         str | None = None
    plan_feedback_history: list[str] = []
    mode:                  str = "unknown"
    mode_order:            list[str] = []
    update_iterator:       IteratorState = IteratorState()
    create_iterator:       IteratorState = IteratorState()
    pm_input:              str | None = None
    current_node:          str = "EntryNode"
    tool_calls:            list[ToolCallRecord] = []      # accumulated during session
    node_transitions:      list[NodeTransition] = []      # accumulated during session
    start_time:            str | None = None               # ISO 8601
```

### `ToolCallRecord` and `NodeTransition`
Accumulated during the session in `PMAgentState`, then written to DynamoDB at session end.

```python
class ToolCallRecord(BaseModel):
    tool_name:  str
    params:     dict
    timestamp:  str                          # ISO 8601
    result:     str = "tool response received"   # never store full response

class NodeTransition(BaseModel):
    node:       str
    timestamp:  str                          # ISO 8601
```

### `SessionRecord`
Written to DynamoDB (`pmm-agent-sessions` table) once at session end. Never updated after write.

```python
class SessionRecord(BaseModel):
    session_id:        str                   # partition key
    pm_name:           str
    pm_email:          str
    mode:              str                   # "release" | "adhoc"
    release_label:     str | None = None
    start_time:        str                   # ISO 8601
    end_time:          str                   # ISO 8601
    status:            str                   # "completed" | "restarted"
    tool_calls:        list[ToolCallRecord] = []
    node_transitions:  list[NodeTransition] = []
```

### `AgentDeps`
Runtime-only dependency container. Never serialised, reconstructed each turn.

```python
@dataclass
class AgentDeps:
    lambda_client:  LambdaClient         # shared boto3 Lambda invoker
    llm_model:      OpenAIModel          # PydanticAI model (configured from PROVIDERS)
    model_settings: dict                 # {"extra_body": {"reasoning_effort": "low"}}
    pm_context:     PMContext             # typed struct, not raw Markdown
    session_id:     str                   # passed to egain Lambda for token lookup
    release_label:  str | None
    aha_skill:      str                   # SKILL.md content, injected into @agent.instructions
    egain_skill:    str                   # SKILL.md content, injected into @agent.instructions
```

---

## 8. Infrastructure

```
Internet ──► CloudFront ──► S3 (frontend: PM dropdown + chat widget)
    │
    └──► ALB (public, HTTPS) ──► ECS Fargate
                                      │
                     ┌────────────────┼─────────────────┐
                     │                │                  │
              ElastiCache       Secrets Manager          S3
                Redis           (aha, egain,        (context bucket
               (live session,    anthropic)          company-context.md)
               token TTL)                                 │
                     │                             Lambda (context-refresher)
                     │                                    │
                DynamoDB                       POST /internal/context/invalidate
          (pmm-agent-sessions                       (back to ECS)
           session history,
           written at end)
                     │
           ┌─────────┴──────────┐
      Aha API              eGain Knowledge API v4
  (egain.aha.io)        (apidev.egain.com, read-only)
```

All ECS tasks run in private subnets. Redis is accessible only from `sg-orchestration`. There are no public-facing services other than the ALB and CloudFront.

### Infrastructure Decision Log

| Component | Choice | Ruled Out | Reason |
|---|---|---|---|
| Orchestration | ECS Fargate | Lambda | HITL sessions span multiple HTTP requests. Lambda's 15-min timeout and stateless model don't fit. |
| API clients | Single generic Lambda (`pmm-skill-client`) | Per-skill Lambdas, imported Python classes, MCP servers | One Lambda handles all skills — auth config is passed as `api_config` in each invocation payload (defined in each skill's `tools.py`). Adding a new skill requires zero Lambda code changes. Trade-off: ~50-200ms overhead per call and no client-side rate limiting — accepted for simplicity. |
| Skill definitions | Repo (`config/skills/`) | S3-hosted Markdown | Skills change with code. Repo versioning and deploy pipeline are the right lifecycle. S3 is only for content that changes independently of code. |
| Context refresher | Lambda | ECS sidecar, polling | S3 event → HTTP call is a perfect Lambda shape: stateless, short-lived, event-driven. |
| HITL session state (live) | ElastiCache Redis | DynamoDB, RDS | In-memory speed for frequent reads per turn. TTL auto-expiry. Simple key-value access pattern. |
| Session history (audit) | DynamoDB | Redis, RDS, S3 | Write-once at session end. Simple key-value. Pay-per-request fits low volume. No TTL needed — records persist indefinitely. |
| Company context | S3 versioned bucket | Git, Parameter Store | Updates without deploy. Version rollback. File is managed content, not code. |
| Secrets | Secrets Manager | Env vars | IAM-scoped access. Rotation support. Audit trail. Credentials never in container definition. `pmm-skill-client` Lambda fetches credentials per invocation using `credentials_secret` from the skill's `API_CONFIG`. |

---

## 9. PM and Product Reference

### PM Ownership

| PM | Email | Products | Role | In Dropdown |
|---|---|---|---|---|
| Prasanth Sai | prasanth.sai@egain.com | AIA, ECAI | PM — AI Agent + AI Services | Yes |
| Aiushe Mishra | aiushe.mishra@egain.com | AIA | PM — AI Agent | Yes |
| Carlos España | carlos.espana@egain.com | ECAI | PM — AI Services | Yes |
| Varsha Thalange | varsha.thalange@egain.com | AIA, ECAI, ECKN, ECAD | PM Manager — full visibility | Yes |
| Ankur Mehta | ankur.mehta@egain.com | ECKN | PM — Knowledge | No |
| Peter Huang | peter.huang@egain.com | ECKN | PM — Knowledge | No |
| Kevin Dohina | kevin.dohina@egain.com | ECAD | PM — Advisor Desktop | No |

**Frontend dropdown:** Only the four PMs marked "Yes" appear in the chat widget's PM selection dropdown. The selected PM name maps to their email via `company-context.md`, which determines product ownership and release context.

### Aha Products

| Product | Code | Aha URL | Release Type |
|---|---|---|---|
| AI Agent | `AIA` | `egain.aha.io/products/AIA` | Version tags (`AIA x.x.x`) |
| AI Services | `ECAI` | `egain.aha.io/products/ECAI` | Standard (`YY.MM`) |
| Knowledge | `ECKN` | `egain.aha.io/products/ECKN` | Standard (`YY.MM`) |
| Advisor Desktop | `ECAD` | `egain.aha.io/products/ECAD` | Standard (`YY.MM`) |

**AIA vs standard:** AIA releases are not tracked via the Aha Release field. Instead, individual features are tagged with version strings (`AIA 1.2.0`, `AIA 2.0.0`). The agent detects this via `release_field_type = "aia_version_tag"` in `PMContext.aha_mappings` and uses `aha_get_release_features` with a `tag` parameter instead of a `release_id`. Both paths use the `fields` query parameter to return full feature details (description, custom_fields, tags, attachments) in a single API call — no per-feature detail fetches needed.

**ECKN + ECAI dependency:** Some ECKN features have ECAI component dependencies. The agent flags these in the plan and notes that Prasanth Sai or Carlos España should review.

---

## 10. Security Considerations

### 10.1 Credential Isolation

**Credentials never touch the orchestration service.** API keys are fetched from Secrets Manager by `pmm-skill-client` Lambda at invocation time, using the `credentials_secret` declared in each skill's `API_CONFIG` (defined in `tools.py`). They never appear in Redis, in any tool description, in any system prompt, or in any log. The Lambda IAM role is scoped to `pmm-agent/*` secrets only. The ECS task role has `lambda:InvokeFunction` permission on `pmm-skill-client` but no access to API credentials.

### 10.2 Tool Sandboxing — Only Skill Scripts Execute

The agent can only execute code that exists in `config/skills/*/scripts/` and only via the `pmm-skill-client` Lambda. There are three layers of enforcement:

1. **PydanticAI tool registration:** Only tools defined in `tools.py` files and explicitly passed to `Agent(tools=AHA_TOOLS)` are available. The LLM cannot call arbitrary functions — it can only call registered tools.

2. **Lambda allowlist:** The `pmm-skill-client` Lambda validates that the `api_config.name` in the payload matches a known skill (`aha`, `egain`, etc.). Unknown skill names are rejected. The Lambda does not execute arbitrary code — it makes HTTP requests to predefined `base_url` endpoints.

3. **No shell access:** The orchestration service has no `Bash` tool, no `exec()`, no `subprocess` — the LLM cannot execute arbitrary commands. Tool functions only call `lambda_client.invoke_skill_lambda()`, which is a boto3 Lambda invoke.

### 10.3 Prompt Injection Defense

PM input flows through multiple layers before reaching the LLM:

1. **Input sanitization middleware** (FastAPI): Strips control characters, limits input length (max 2000 chars), rejects inputs containing known injection patterns (`ignore previous`, `system prompt`, `<|im_start|>`).

2. **Structured output enforcement** (PydanticAI): Every agent returns a typed Pydantic `result_type`. The LLM cannot return arbitrary text — it must produce valid structured output that matches the schema. If it doesn't, PydanticAI raises a validation error.

3. **Tool description isolation:** Tool docstrings (what the LLM sees) never contain credentials, base URLs, or auth details. They describe WHAT the tool does, not HOW it authenticates.

4. **State mutation via `ctx.state` only:** Nodes mutate state via `ctx.state` (the `PMAgentState`). The PM's input is stored in `ctx.state.pm_input` and consumed by the next node — it does not persist across multiple nodes or accumulate in the prompt.

### 10.4 Environment Variable Protection

- `.env` files are in `.gitignore` — never committed
- The orchestration service reads env vars at startup only (`config.py`) — they are not accessible to tool functions or LLM prompts
- The Lambda has its own env vars (`EGAIN_API_HOST`, `AWS_DEFAULT_REGION`) set via Terraform — not from `.env`
- Development-time protection: `.claude/hooks/security-validator.sh` blocks Claude Code from reading `.env` files or dumping env vars during development

### 10.5 Portal & Data Safety

**eGain read-only:** No write APIs are available or used. The agent presents HTML content in chat — the PM manually applies it in the portal. `OutputReviewNode` (HITL Gate 6) is the final PM gate before session ends.

**PM isolation:** Each PM operates in an independent session. `PMAgentState` keys include `session_id` — there is no shared state between sessions.

**PM identity verification:** The agent resolves the PM's owned products from `company-context.md` at session start. A PM will only see releases and articles relevant to their assigned products.

**Aha service account:** The Aha API key is a dedicated service account key — not a personal key. This maintains accurate audit logs in Aha and survives individual key rotation.

### 10.6 Development-Time Hooks (`.claude/hooks/`)

The repo includes Claude Code hooks in `.claude/settings.json` that protect developers during development:

- **Block destructive commands:** `rm -rf /`, `DROP TABLE`, force-push to main
- **Block env var dumps:** `printenv`, `echo $API_KEY`, etc.
- **Block sensitive file reads:** `.env`, `.pem`, `terraform.tfstate`
- **Block secret leaks in code:** Detects API key patterns (AWS, GitHub, Anthropic) in content being written
- **Block unknown HTTP hosts:** Only allow `curl`/`wget` to known hosts (localhost, egain.com, aha.io, etc.)

---

## 11. Extension Roadmap

New integrations require no graph changes — only a new skill folder.

| Phase | Capability | Skill Folder | Node Extended |
|---|---|---|---|
| 1 (current) | eGain portal article reads + suggest create/update with HTML output | `config/skills/egain/` | `PortalContextAgentNode`, `OutputAgentNode` |
| 2 | Jira issue context in plan (acceptance criteria, test notes) | `config/skills/jira/` | `ReleaseContextAgentNode` |
| 2 | Mailchimp email campaign draft from release | `config/skills/mailchimp/` | `OutputAgentNode` |
| 3 | HubSpot blog post draft | `config/skills/hubspot/` | `OutputAgentNode` |
| 3 | Slack release summary post | `config/skills/slack/` | `OutputAgentNode` |
| 3 | Zendesk / Intercom article sync | `config/skills/zendesk/` | `PortalContextAgentNode` |

Adding a new skill folder: create `SKILL.md`, `tools.py` (with tool functions and an `API_CONFIG` constant), `scripts/` (optional helpers), `references/api.md`, then import the skill's `*_TOOLS` list in the target agent node. No Lambda changes needed — `pmm-skill-client` reads auth config from the `api_config` in each invocation payload. See Section 14 of `pmm-ai-agent-guide.md` for step-by-step instructions.

### 11.1 Future: Compound Request Handling

Currently the graph handles one flow per session (one release, or one ad-hoc article change). The `DocumentPlan` + update/create iterators already serve as a task tracker within a single flow — breaking a release into per-article tasks with individual confirmation.

When multi-capability support is added (Phase 2+), PMs may give compound requests:
> "Update the release notes for AIA 1.2.0, send the email campaign, and post to Slack"

This is three different skills/flows. At that point, add a **TaskDecompositionNode** after EntryNode that:
1. Detects compound intent (multiple skills/actions in one PM message)
2. Breaks it into a task queue: `[portal_update, email_campaign, slack_post]`
3. Executes each task sequentially through the appropriate graph subflow
4. Tracks completion status per task

This is NOT needed for Phase 1 (4 PMs, single flow per session). The `DocumentPlan` is the task tracker for now. Add `TaskDecompositionNode` when the first multi-skill flow is implemented.

---

*Build guide: `docs/pmm-ai-agent-guide.md`*  
*Diagrams: `docs/pmm-ai-agent-architecture-diagrams.md`*  
*Repository map: `REPO.md`*
