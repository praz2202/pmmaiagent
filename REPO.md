# PMM AI Agent — Repository Map

**Read this file first.** This is the canonical reference for every file in this
repository — what it does, what it imports, what reads it, and what env vars it
needs. Intended for Claude Code and developers navigating an unfamiliar codebase.

> **Primary build guide:** `docs/pmm-ai-agent-guide.md` — the single sequential
> document to follow when building the project. Sections 0–14, every step executable,
> every step has a checkpoint. Start there, use this file for navigation.

---

## Repository Purpose

Internal tool that helps eGain Product Managers keep portal documentation in sync
with product releases. PMs chat with the agent; it fetches release specs from Aha,
reads existing eGain portal articles (read-only API), proposes an update plan, iterates
article-by-article with the PM, and presents the final HTML content with a recommendation
to create a new article or update an existing one — the PM applies changes manually in the portal.

Single deployable service (`services/orchestration`) + three self-contained skill
folders (`config/skills/aha`, `config/skills/egain`, `config/skills/company-context`).

---

## Top-Level Layout

```
pmm-ai-agent/
├── REPO.md                     ← YOU ARE HERE — read before navigating anything else
├── README.md                   ← Human-facing project overview
├── .env.example                ← Safe defaults, committed. Copy to .env.local and fill in keys
├── .env.local                  ← Git-ignored. Your local dev credentials
├── .claude/
│   ├── settings.json           ← Claude Code hooks: blocks .env reads, destructive commands, secret leaks
│   └── hooks/
│       └── security-validator.sh  ← PreToolUse hook: validates Bash commands and file access
├── docker-compose.yml          ← Local dev: orchestration + redis
├── pyproject.toml              ← Python workspace config, test settings, ruff config
│
├── prompts/                    ← All LLM prompt templates — externalized, easy to iterate
│   ├── COMPACTION_PROMPT.txt   ← Context window compaction summary template
│   ├── entry_node.txt          ← EntryNode system prompt
│   ├── release_confirm_node.txt ← ReleaseConfirmNode system prompt
│   ├── release_context_node.txt ← ReleaseContextAgentNode system prompt (includes {aha_skill})
│   ├── portal_context_node.txt  ← PortalContextAgentNode system prompt (includes {egain_skill})
│   ├── plan_gen_node.txt       ← PlanGenNode system prompt
│   ├── plan_review_node.txt    ← PlanReviewNode system prompt
│   ├── output_node.txt         ← OutputAgentNode system prompt
│   ├── output_review_node.txt  ← OutputReviewNode system prompt
│   ├── adhoc_router_node.txt   ← AdHocRouterNode system prompt
│   ├── suggest_node.txt        ← SuggestNode system prompt (includes {egain_skill})
│   ├── update_feedback_node.txt ← UpdateFeedbackNode system prompt
│   └── refine_node.txt         ← RefineUpdate/RefineCreate system prompt
│                                  All loaded via: context_loader/prompt_loader.py → load_prompt("name")
│                                  Templates use {variable} placeholders formatted at runtime
│
├── config/                     ← Skill definitions — versioned with code, never in S3
├── context/                    ← company-context.md — uploaded to S3, changes without deploy
├── docs/                       ← Reference documents (do not build from these)
│   ├── pmm-ai-agent-guide.md               ← PRIMARY BUILD GUIDE — follow this step by step
│   ├── pmm-ai-agent-architecture-diagrams.md ← 11 Mermaid diagrams
│   ├── pmm-ai-agent-architecture.md         ← v1.0 prose architecture (superseded by diagrams)
│   └── pmm-ai-agent-devops-plan.md          ← CI/CD pipeline detail
├── frontend/                   ← Static chat widget — deployed to S3 + CloudFront
├── infrastructure/             ← Terraform modules + deploy scripts
├── services/orchestration/     ← The only deployable service
├── lambdas/                    ← Lightweight async helpers
└── tests/                      ← Full test suite: unit, functional, integration, smoke, e2e
```

---

## `config/` — Skill Folders

Each skill is a self-contained folder following the Anthropic skills standard:
`SKILL.md` (instructions for the LLM) + `tools.py` (Python tool functions with typed params + docstrings) +
`scripts/` (Python client code) + `references/` (detailed API docs, lazy-loaded).

**Rule:** Auth credentials NEVER appear in any file under `config/`. They live in
`AgentDeps`, fetched from AWS Secrets Manager at session start.

```
config/
└── skills/
    │
    ├── aha/                            ← Everything needed to call the Aha API
    │   ├── SKILL.md                    ← LLM instructions: tool overview, gotchas, progressive disclosure links
    │   │                                  Read by: skill_loader.py → stored in AgentDeps.aha_skill
    │   │                                  Injected in: release_context_agent.py @agent.instructions
    │   ├── tools.py                    ← 6 Python tool functions + AHA_API_CONFIG constant
    │   │                                  Imported by: release_context_agent.py via Agent(..., tools=AHA_TOOLS)
    │   │                                  Tools registered on: ReleaseContextAgentNode agent
    │   ├── scripts/
    │   │   └── aha_client.py           ← Aha-specific helpers (AIA path resolution, tag detection)
    │   │                                  Used by: pmm-skill-client Lambda (optional import)
    │   │                                  Auth: Declared in AHA_API_CONFIG (type=basic, secret=pmm-agent/aha-api-key)
    │   │                                  Rate limiting: None — 429 errors propagate to the agent
    │   └── references/
    │       ├── api.md                  ← Aha field paths, rate limits, release name formats
    │       ├── aia-releases.md         ← AIA version tag detection, tag-based fetch pattern
    │       └── filtering.md            ← documents_impacted filter, cross-product flags, Jira URL paths
    │                                      All loaded lazily via progressive disclosure from SKILL.md
    │
    ├── egain/                          ← Everything needed to call the eGain Knowledge API v4 (read-only)
    │   ├── SKILL.md                    ← LLM instructions: read API usage, gotchas, output recommendations
    │   │                                  Read by: skill_loader.py → stored in AgentDeps.egain_skill
    │   │                                  Injected in: portal_context_agent.py
    │   ├── tools.py                    ← 2 read-only Python tool functions + EGAIN_API_CONFIG constant
    │   │                                  Imported by: portal_context_agent.py via Agent(..., tools=EGAIN_TOOLS)
    │   │                                  Auth: on-behalf-of-customer (client_app + client_secret from Secrets Manager)
    │   │                                  No write operations — agent presents HTML to PM for manual apply
    │   └── references/
    │       ├── api.md                  ← eGain Knowledge API v4 reference, endpoints, auth
    │       └── html-format.md          ← Portal HTML format rules, image handling, article structure
    │                                      Loaded lazily via progressive disclosure from SKILL.md
    │
    └── company-context/                ← Instructions for using parsed company context
        ├── SKILL.md                    ← PM→product mapping, release type rules, cross-product flags
        │                                  Read by: skill_loader.py (loaded but injected selectively)
        └── references/
            └── parsing.md              ← Markdown table format, PMContext field extraction patterns
                                           Used by: s3_loader.py as authoritative parsing spec
```

---

## `context/` — S3 Content

```
context/
└── company-context.md              ← PM ownership, Aha mappings, release rules, portal folders
                                       Deployed to: S3 bucket egain-pmm-agent-context-{account_id}
                                       Loaded by: s3_loader.load_company_context()
                                       Cache: 5-minute process-level TTL
                                       Update without redeploy: YES — aws s3 cp ... then POST /internal/context/invalidate
                                       NEVER injected raw into prompts — parsed into PMContext struct
```

**Why S3 and not the repo?** PM org changes (new hire, product transfer) happen
independently of code changes. Uploading to S3 updates the running service immediately
without a deploy. Skills change with code — they stay in the repo.

---

## `services/orchestration/` — The Only Service

FastAPI app + PydanticAI graph + Redis session manager. Deployed as a single ECS Fargate task.

```
services/orchestration/
│
├── Dockerfile                      ← python:3.11-slim, exposes 8000, uvicorn CMD
├── requirements.txt                ← pydantic-ai, openai, fastapi, uvicorn, redis, boto3, httpx, structlog, logfire
├── requirements-dev.txt            ← pytest, pytest-asyncio, ruff, mypy
│
├── main.py                         ← FastAPI app, lifespan hooks, all HTTP endpoints
│   Routes:
│     POST /sessions/start          → creates session (pm_name from dropdown), runs EntryNode, returns session_id
│     POST /sessions/{id}/respond   → loads state, reconstructs AgentDeps, resumes Graph.iter()
│     POST /sessions/{id}/end       → writes SessionRecord to DynamoDB, deletes Redis keys
│     GET  /sessions/{id}/status    → returns current_node, mode, pm_context
│     GET  /sessions/{id}/stream    → SSE heartbeat stream (progress during slow tool-agent nodes)
│     DELETE /sessions/{id}         → deletes Redis keys for session
│     GET  /health                  → {"status":"healthy","version":"1.0.0"}
│     POST /internal/context/invalidate → clears s3_loader TTL cache (called by Lambda)
│     GET  /internal/tools/list     → lists all registered tool names (smoke test)
│   Graph: graph/graph.py — Graph(nodes=[...]) constructed at module level; Graph.iter() for HITL
│             Graph.iter() runs nodes until HITL pause or End
│             Node imports are deferred inside if-blocks — avoids circular imports
│   Observability: structlog JSON logs on every node entry/exit; Logfire traces LLM + tool calls
│   Env vars: all of the below, REDIS_URL, APP_ENV
│
├── config.py                       ← Loads env vars, provides typed config object
│   LLM providers: PROVIDERS dict (gemini, anthropic, openai)
│     DEFAULT_PROVIDER = "gemini"   ← change this to switch all agent nodes
│     DEFAULT_MODEL_SETTINGS = {"extra_body": {"reasoning_effort": "low"}}
│     Each provider: name, model, base_url, api_key_env, credentials_secret
│   Env vars: AHA_SUBDOMAIN, EGAIN_API_HOST, CONTEXT_BUCKET, AWS_DEFAULT_REGION,
│             REDIS_URL, LOG_LEVEL, FRONTEND_ORIGIN_DEV, FRONTEND_ORIGIN_PROD,
│             GEMINI_API_KEY, CLAUDE_API_KEY, OPENAI_API_KEY (local overrides)
│
├── compaction.py                   ← Context window management — compacts message history
│   Key function: maybe_compact(state, model) — called between turns
│     Triggers at 90% of 480k chars (432k). Permanently replaces history with
│     [summary ≤ 12k tokens] + [last turn]. Leaves ~90% context free.
│   cap_tool_response(name, response) — enforces 60k char limit per tool response
│   count_message_chars(messages) — counts total chars for threshold check
│
├── tools/                          ← AgentDeps only (tool functions live in config/skills/*/tools.py)
│   ├── __init__.py
│   └── deps.py                     ← AgentDeps dataclass + build_deps() factory
│       Imports: session.models.PMContext
│       Key function: build_deps(pm_context, session_id, release_label)
│         → returns AgentDeps with shared LambdaClient (boto3) + session_id
│         → no API client objects — Lambdas handle auth independently
│       Process singletons (lru_cache): _get_lambda_client(), _get_skill_md()
│       Env vars: AWS_DEFAULT_REGION
│       Tool registration: each agent node imports tools directly from config/skills/*/tools.py
│                          e.g. Agent(..., tools=AHA_TOOLS) in release_context_agent.py
│                          How auth works: tool_fn receives ctx: RunContext[AgentDeps]
│                          builds payload with api_config dict from tools.py
│                          calls ctx.deps.lambda_client.invoke_skill_lambda("pmm-skill-client", payload)
│                          Lambda reads api_config.auth → fetches credentials from Secrets Manager
│                          LLM never sees credentials
│
├── session/                        ← Session state models + Redis manager
│   ├── __init__.py
│   ├── models.py                   ← All Pydantic models (serialised to Redis)
│   │   Key models:
│   │     AhaMapping       — per-product Aha config (product key, release_field_type)
│   │     PMContext        — parsed PM data (name, products, aha_mappings, portal_folders)
│   │     ArticlePlan      — one article update or create plan
│   │     IteratorState    — per-article loop: articles[], current_index, confirmed_articles[]
│   │     DocumentPlan     — full plan: articles_to_update[] + articles_to_create[]
│   │     PMAgentState     — REDIS-SERIALISED session state (NO credentials, NO raw context)
│   │   NOT in models.py:
│   │     AgentDeps        — in tools/deps.py (runtime only, never serialised)
│   │
│   ├── redis_client.py             ← SessionManager class (live session state)
│   │   Key: session:{session_id}  TTL: 86400s (24h)
│   │   Env vars: REDIS_URL
│   │
│   └── session_history.py         ← SessionHistoryManager class (DynamoDB)
│       Table: pmm-agent-sessions  PK: session_id
│       Key function: save_session_record(state, status) → writes SessionRecord to DynamoDB
│       Called by: POST /sessions/{id}/end and DoneNode
│       Tool call results stored as "tool response received" — never full response
│       Env vars: AWS_DEFAULT_REGION
│
├── context_loader/                 ← Load and parse external context
│   ├── __init__.py
│   ├── s3_loader.py                ← Loads company-context.md from S3, parses → PMContext
│   │   Key function: load_company_context(pm_email) → PMContext
│   │   Cache: 5-minute process-level TTL (_cache dict, not lru_cache — needs invalidation)
│   │   Invalidation: invalidate_cache() called by POST /internal/context/invalidate
│   │   Parsing: _parse_pm_ownership_table, _parse_aha_mappings_table,
│   │            _parse_portal_folders_table, _parse_cadence_rules, _parse_upcoming_releases
│   │   Env vars: CONTEXT_BUCKET, AWS_DEFAULT_REGION
│   │
│   └── skill_loader.py             ← Loads SKILL.md and references/ from config/skills/
│       Key functions:
│         load_skill_md(skill_name)               → str  (cached indefinitely — lru_cache)
│         load_skill_reference(skill_name, fname) → str  (lazy, not cached)
│       Path: config/skills/{skill_name}/SKILL.md
│             config/skills/{skill_name}/references/{filename}
│
└── graph/                          ← PydanticAI Graph orchestration
    ├── __init__.py
    ├── graph.py                    ← pmm_graph = Graph(nodes=[...], state_type=PMAgentState, deps_type=AgentDeps)
    │                                  No dispatch() — Graph handles routing via BaseNode return types
    │                                  is_hitl_node() — checks if next node needs PM input
    │                                  get_node_class() — resolves node class from string (for resume)
    ├── state.py                    ← GraphState wrapping PMAgentState
    └── nodes/                      ← One file per graph node
        ├── __init__.py
        │
        ├── entry.py                ← EntryNode (BaseNode — LLM reasoning)
        │   Purpose: identify PM, load context, route to release or ad-hoc
        │   HITL: No — auto-advances after greeting if intent is clear
        │   Routes to: ContextSetupNode | AdHocRouterNode
        │
        ├── context_setup.py        ← ContextSetupNode (BaseNode — Python logic, no LLM)
        │   Purpose: validates pm_context is loaded, no LLM call
        │   HITL: No
        │   Routes to: ReleaseConfirmNode
        │
        ├── release_confirm.py      ← ReleaseConfirmNode  ★ HITL GATE #1
        │   Purpose: list active releases for PM's products, PM picks one
        │   HITL: YES — pauses, awaits PM input
        │   For AIA: lists AIA version tags (not standard releases)
        │   On confirm: sets state.release_id + state.release_label
        │   Routes to: ReleaseContextAgentNode
        │
        ├── release_context_agent.py ← ReleaseContextAgentNode  (Tool-Agent Node)
        │   Purpose: fetch all Aha release data (features, specs, images, Jira URLs)
        │   Agent: Agent[AgentDeps, ReleaseContextResult]
        │   Tools: imported from config/skills/aha/tools.py — all 6 Aha tools
        │   Instructions: @agent.instructions injects pm_context Aha mappings + aha_skill
        │   HITL: No — runs autonomously, may call 10-20 Aha API calls
        │   Slow: Yes (30-60s) — SSE heartbeats sent during run
        │   Routes to: PortalContextAgentNode
        │
        ├── portal_context_agent.py  ← PortalContextAgentNode  (Tool-Agent Node)
        │   Purpose: read eGain portal — get articles in topics, get article content
        │   Agent: Agent[AgentDeps, PortalContextResult]
        │   Tools: imported from config/skills/egain/tools.py — 2 read-only eGain tools
        │   Instructions: injects portal context (topic IDs from company-context.md) + egain_skill
        │   HITL: No
        │   Routes to: PlanGenNode
        │
        ├── plan_gen.py             ← PlanGenNode
        │   Purpose: generate DocumentPlan (articles_to_update + articles_to_create)
        │   Input: state.aha_specs + state.portal_articles + pm_context
        │   No tools — pure LLM reasoning call
        │   Re-runs if state.plan_feedback is set (PM edited the plan)
        │   Routes to: PlanReviewNode
        │
        ├── plan_review.py          ← PlanReviewNode  ★ HITL GATE #2
        │   Purpose: present full plan to PM for review
        │   HITL: YES — pauses, awaits PM input
        │   On confirm: advances to ModeSelectNode
        │   On edit: stores feedback in state.plan_feedback, loops back to PlanGenNode
        │
        ├── mode_select.py          ← ModeSelectNode  ★ HITL GATE #3
        │   Purpose: ask PM — start with updates or new articles first?
        │   HITL: YES — pauses, awaits PM input
        │   Sets: state.mode_order = ["updates","creates"] or ["creates","updates"]
        │   Routes to: ShowUpdatePlan | ShowCreatePlan (based on mode_order[0])
        │
        ├── update_iterator.py      ← UpdateIterator nodes (4 node functions in one file)
        │   Nodes: ShowUpdatePlan | UpdateFeedbackGate (HITL #4) | RefineUpdate | AdvanceUpdateIndex
        │   Purpose: per-article loop for updates — show plan → PM feedback → refine → confirm → next
        │   HITL: UpdateFeedbackGate — YES per article
        │   State used: state.update_iterator (IteratorState)
        │   When done: routes to ShowCreatePlan or OutputAgentNode depending on mode_order
        │
        ├── create_iterator.py      ← CreateIterator nodes (4 node functions in one file)
        │   Same structure as update_iterator.py but for new article creation
        │   Nodes: ShowCreatePlan | CreateFeedbackGate (HITL #5) | RefineCreate | AdvanceCreateIndex
        │   State used: state.create_iterator (IteratorState)
        │   When done: routes to OutputAgentNode
        │
        ├── output_agent.py         ← OutputAgentNode  (LLM Reasoning Node)
        │   Purpose: present final HTML content for each confirmed article to PM
        │   Agent: Agent[AgentDeps, OutputResult]
        │   No tools — pure LLM reasoning (no eGain write APIs exist)
        │   Recommends: create new article / update existing / both options (if ambiguous)
        │   Outputs: article HTML + recommendation for PM to manually apply in portal
        │   Routes to: OutputReviewNode
        │
        ├── output_review.py        ← OutputReviewNode (BaseNode — LLM reasoning) ★ HITL Gate 6
        │   Purpose: PM reviews final HTML output — approve or request changes
        │   HITL: YES — pauses, awaits PM approval or feedback
        │   Routes to: DoneNode (approved) | OutputAgentNode (feedback → re-runs)
        │
        ├── done.py                  ← DoneNode (BaseNode — Python logic)
        │   Purpose: returns End[str], session complete, writes to DynamoDB
        │
        ├── adhoc_router.py         ← AdHocRouterNode  ★ HITL (ad-hoc flow entry)
        │   Purpose: ask PM — do they know the article, or should the agent suggest?
        │   Routes to: AskArticleNode | SuggestNode
        │
        ├── ask_article.py          ← AskArticleNode
        │   Purpose: collect article ID (update) or folder (create) from PM
        │   Populates: state.update_iterator or state.create_iterator with one article
        │   Routes to: ShowUpdatePlan | ShowCreatePlan
        │
        └── suggest.py              ← SuggestNode
            Purpose: search portal articles (read-only), suggest best match to PM
            Uses: egain_get_articles_in_topic, egain_get_article_by_id via egain tools
            Routes to: ShowUpdatePlan (accepted) | SuggestNode again (rejected)
```

---

## `tests/` — Test Suite

```
tests/
├── conftest.py                     ← Shared pytest fixtures (auto-loaded by pytest)
│   Fixtures provided:
│     set_test_env (autouse)        — injects safe env vars, prevents real secrets use
│     mock_redis                    — in-memory dict Redis, exposes (mock, store) tuple
│     mock_aha_http                 — httpx.MockTransport routing Aha paths to fixtures
│     mock_egain_http               — httpx.MockTransport routing eGain paths to fixtures
│     mock_s3                       — boto3 patch returning fixture files
│     mock_secrets_manager (autouse) — prevents any real AWS calls
│     aha_fixtures, egain_fixtures  — loaded JSON fixtures (session scope)
│     base_url, run_live            — CLI options for integration/smoke/e2e
│
├── pytest.ini                      ← Markers, asyncio_mode=auto, testpaths
│
├── fixtures/
│   ├── mock_aha_responses.json     ← Canned Aha API responses (releases, features, attachments)
│   ├── mock_egain_responses.json   ← Canned eGain Portal responses (topics, articles, drafts)
│   ├── mock_company_context.md     ← Test company-context.md (real PMs, real product codes)
│   └── mock_state.py              ← Factory functions: make_agent_state(), make_article_plan(), etc.
│
├── unit/                           ← Fast, fully mocked. No network, no AWS. Run: pytest tests/unit/
│   ├── aha/
│   │   ├── test_releases.py        ← aha_list_releases, aha_get_release_notes_features, AIA filter
│   │   ├── test_tags.py            ← AIA version tag parsing: parse_aia_version_from_tags()
│   │   └── test_features_and_components.py ← specs, attachments, jira_url, components
│   ├── egain/
│   │   ├── test_egain_read.py      ← verifies read-only eGain tools return correct structure
│   │   └── test_search_and_topics.py ← list topics, search, articles by topic, article summary
│   ├── orchestration/
│   │   ├── test_models.py          ← Pydantic model validation, IteratorState.is_done(), round-trips
│   │   ├── test_session.py         ← Redis save/get/delete, TTL=86400, key format session:{id}
│   │   ├── test_update_iterator.py ← confirm/yes/lgtm → AdvanceUpdateIndex; full 3-article loop
│   │   └── test_api_endpoints.py  ← FastAPI TestClient: all endpoints, session isolation
│   └── tools/
│       ├── test_tools.py            ← Tool function imports, tool names, descriptions
│       ├── test_aha_client.py      ← AhaClient: retry logic, rate limiter, response extraction
│       └── test_egain_read_api.py ← eGain read-only API: basic_onbehalf auth, get articles/topics
│
├── functional/                     ← Real graph transitions, LLM mocked. Run: pytest tests/functional/
│   ├── test_hitl_gates.py          ← All 6 HITL gates: pause, confirm routes, edit routes, feedback
│   ├── test_release_flow.py        ← EntryNode→...→OutputAgentNode full sequence
│   ├── test_aia_version_flow.py    ← AIA-specific: version tag fetch, not standard release
│   └── test_adhoc_flow.py          ← AdHocRouterNode→AskArticleNode/SuggestNode→iterators
│
├── integration/                    ← Real dev APIs. Requires: --run-live flag
│   ├── test_aha_api.py             ← Live Aha: real releases, real features, real field filtering
│   └── test_egain_api.py           ← Live eGain: create real draft, verify source field persisted
│
├── smoke/                          ← Post-deploy health checks. Run after every deploy.
│   └── test_smoke.py              ← /health, session start, tool registry, SLA checks (<90s total)
│                                     Run: pytest tests/smoke/ --base-url=https://your-alb.com
│
└── e2e/
    └── test_release_session.py    ← Full PM session: start→release→plan→iterate→drafts published
                                      Run: pytest tests/e2e/ --run-live --base-url=https://your-alb.com
```

---

## `infrastructure/` — AWS Infrastructure

```
infrastructure/
├── terraform/
│   ├── main.tf                     ← Root module — calls all sub-modules
│   ├── variables.tf                ← aws_account_id, aws_region, env, vpc_cidr
│   ├── outputs.tf                  ← redis_endpoint, public_alb_dns_name, ecs_cluster_name,
│   │                                  private_subnet_ids, orchestration_sg_id
│   ├── terraform.tfvars.example    ← Copy to terraform.tfvars and fill in account ID
│   └── modules/
│       ├── networking/             ← VPC, public/private subnets (2 AZs), NAT, ALBs, security groups
│       │   ├── main.tf             ← sg-orchestration, sg-redis (inbound only from orchestration)
│       │   └── variables.tf
│       ├── redis/                  ← ElastiCache Redis 7.x (cache.t4g.small, single node, private)
│       │   ├── main.tf
│       │   └── variables.tf
│       ├── dynamodb/              ← DynamoDB table for session history
│       │   ├── main.tf             ← pmm-agent-sessions (PK: session_id, pay-per-request)
│       │   └── variables.tf
│       ├── s3/                     ← Context bucket (versioned, encrypted, private)
│       │   ├── main.tf             ← Also creates S3 + CloudFront for frontend
│       │   └── variables.tf
│       ├── secrets/                ← Secrets Manager stubs (values set manually)
│       │   ├── main.tf             ← pmm-agent/aha-api-key, pmm-agent/egain-credentials,
│       │   └── variables.tf           pmm-agent/gemini-api-key, pmm-agent/anthropic-api-key,
│       │                              pmm-agent/openai-api-key
│       ├── ecs/                    ← ECS cluster, task execution IAM role, CloudWatch log groups
│       │   ├── main.tf             ← IAM: ECR pull, Secrets Manager read (pmm-agent/*),
│       │   └── variables.tf           S3 read (context bucket), CloudWatch write
│       └── lambda/                 ← All Lambda definitions
│           ├── main.tf             ← pmm-skill-client (generic skill executor)
│           │                          pmm-context-refresher (S3 event trigger)
│           └── variables.tf
│
├── scripts/
│   ├── install-hooks.sh            ← Copies git-hooks/pre-push to .git/hooks/
│   ├── bootstrap-secrets.sh        ← Creates Secrets Manager entries (run once)
│   ├── push-to-ecr.sh              ← Build + tag + push orchestration image
│   ├── deploy-lambdas.sh           ← Zip + deploy all Lambdas (skill-client, context-refresher)
│   ├── rollback-ecs.sh             ← Rolls ECS service back to previous task definition revision
│   └── upload-context.sh           ← aws s3 cp context/company-context.md to S3
│
└── git-hooks/
    └── pre-push                    ← Runs ruff + unit tests before every git push
```

---

## `lambdas/` — Generic Skill Client + Async Helpers

```
lambdas/
├── skill-client/
│   ├── handler.py                  ← Generic skill executor — handles ALL skill API calls
│   │                                  Invoked by orchestration service via boto3 lambda.invoke
│   │                                  Receives {method, path, params, api_config}
│   │                                  Reads api_config.auth to determine auth strategy:
│   │                                    type=basic       → Secrets Manager → Basic auth header
│   │                                    type=basic_onbehalf → Secrets Manager → on-behalf-of-customer header
│   │                                  Creates fresh httpx client, makes API call, returns result
│   │                                  Adding a new skill requires NO changes to this Lambda
│   └── requirements.txt            ← httpx, boto3
│
└── context-refresher/
    ├── handler.py                  ← Triggered by S3 ObjectCreated event on context/ prefix
    │                                  Calls POST /internal/context/invalidate on orchestration service
    │                                  so running tasks reload company-context.md without restart
    └── requirements.txt            ← httpx only
```

> **Why one generic Lambda instead of per-skill Lambdas?**
> A single `pmm-skill-client` Lambda handles all skills. Auth strategy is read from the
> `api_config` dict constant in each skill's `tools.py`, which is passed in the invocation payload.
> This means adding Jira, Mailchimp, or any other integration requires zero Lambda code
> changes — just a new `tools.py` with the right `api_config` auth section.
>
> Trade-offs: ~50-200ms overhead per call (Lambda invocation + fresh HTTP connection),
> no client-side Aha rate limiting (429 errors propagate to the PM), and one extra
> Redis read per eGain call (Bearer token lookup). These are accepted for simplicity
> and a cleaner security boundary.

---

## `frontend/` — Chat Widget

```
frontend/
├── index.html                      ← Full single-file eGain-branded chat widget
│                                      PM selection dropdown: Prasanth, Aiushe, Carlos, Varsha
│                                      Restart button: ends session → DynamoDB write → back to dropdown
│                                      Connects to orchestration via /sessions/start (pm_name) + /sessions/{id}/respond
│                                      Session end via /sessions/{id}/end (on restart or DoneNode)
│                                      SSE heartbeats via /sessions/{id}/stream
│                                      Deployed to: S3 bucket + CloudFront distribution
├── design-tokens.js                ← eGain Prism design tokens (colors, typography, spacing)
│                                      Imported by index.html
└── assets/
    ├── egain-logo.svg
    └── favicon.ico
```

---

## Key Data Flows

### Session start (multiple PMs simultaneously safe)

```
POST /sessions/start (pm_name, mode)
  └── map pm_name → pm_email via company-context.md
  └── s3_loader.load_company_context(pm_email)
        └── S3: company-context.md → PMContext (TTL-cached 5min, shared across sessions)
  └── build_deps(pm_context, session_id)
        └── _get_lambda_client()          → boto3 Lambda client (shared, stateless)
        └── _get_skill_md("aha")          → SKILL.md content (lru_cache)
        └── _get_skill_md("egain")        → SKILL.md content (lru_cache)
  └── run_entry_node(state, deps)
        └── entry_agent.run(prompt, deps=deps)  ← LLM call
  └── SessionManager.save(session_id, state)    ← Redis: session:{session_id}
  └── return {session_id, message, awaiting_input}
```

### Resumed turn

```
POST /sessions/{id}/respond (input)
  └── SessionManager.get(session_id)             ← Redis: load PMAgentState
  └── build_deps(state.pm_context, session_id,   ← reconstruct AgentDeps
                 state.release_label)
        └── LambdaClient: shared boto3 client (no cost)
        └── No API client objects — Lambdas handle auth independently
  └── Graph.iter(node, state, deps)               ← run graph until HITL pause or End
  └── SessionManager.save(session_id, state)     ← persist updated state
```

### Tool call inside an agent node

```
Agent runs, decides to call aha_get_release_features(product_key="AIA", tag="AIA 1.2.0")
  └── tool_fn(ctx: RunContext[AgentDeps], product_key="AIA", tag="AIA 1.2.0")
        └── lambda_client = ctx.deps.lambda_client
        └── await lambda_client.invoke_skill_lambda("pmm-skill-client", payload)
              └── Lambda: read api_config from payload (type=basic, secret=pmm-agent/aha-api-key)
              └── Lambda: fetch credentials from Secrets Manager
              └── Lambda: fresh httpx client, Basic auth header
              └── Lambda: GET /products/AIA/features?tag=AIA+1.2.0&fields=name,description,custom_fields,tags,attachments
              └── Lambda: returns response data
              └── Lambda returns [full feature objects with all details]
        └── return [full feature objects]
  Single API call returns all features with full details — no per-feature detail fetches.
  The LLM sees only the return value. Credentials never leave the Lambda.
```

### Session end (restart or DoneNode)

```
POST /sessions/{id}/end (reason="completed"|"restarted")
  └── SessionManager.get(session_id)              ← Redis: load final PMAgentState
  └── build SessionRecord from state:
        └── pm_name, pm_email, mode, release_label, start_time
        └── tool_calls: [{tool_name, params, timestamp, result:"tool response received"}]
        └── node_transitions: [{node, timestamp}]
        └── end_time: now, status: reason
  └── SessionHistoryManager.save(session_record)   ← DynamoDB: PutItem
  └── SessionManager.delete(session_id)            ← Redis: delete session key
  └── return {ended: true}
  Frontend returns to PM dropdown → new session on next start
```

---

## Environment Variables Reference

| Variable | Used In | Local Default | Notes |
|---|---|---|---|
| `APP_ENV` | config.py | `local` | `local` / `dev` / `prod` |
| `LOG_LEVEL` | config.py | `debug` | `debug` / `info` / `warn` |
| `REDIS_URL` | redis_client.py | `redis://localhost:6379` | Full Redis URL |
| `AHA_SUBDOMAIN` | Lambda env (pmm-skill-client) | `egain` | Aha subdomain (read by Aha path resolver) |
| `EGAIN_API_HOST` | Lambda env (pmm-skill-client) | `apidev.egain.com` | eGain Knowledge API v4 host |
| `EGAIN_CLIENT_APP` | Lambda env (pmm-skill-client) | *(from Secrets Manager)* | eGain client_app for basic_onbehalf auth |
| `GEMINI_API_KEY` | config.py | *(your key)* | Local override for default LLM provider |
| `CLAUDE_API_KEY` | config.py | *(your key)* | Local override for Anthropic provider |
| `OPENAI_API_KEY` | config.py | *(your key)* | Local override for OpenAI provider |
| `CONTEXT_BUCKET` | s3_loader.py | `egain-pmm-agent-context-{id}` | S3 bucket name |
| `AWS_DEFAULT_REGION` | deps.py, s3_loader.py | `us-east-1` | |
| `AWS_PROFILE` | *(aws cli)* | `pmm-agent-dev` | Local AWS profile |
| `FRONTEND_ORIGIN_DEV` | main.py CORS | `http://localhost:3000` | |
| `FRONTEND_ORIGIN_PROD` | main.py CORS | `https://pmm-agent.egain.com` | |

---

## AWS Resources

| Resource | Name / ID | Purpose |
|---|---|---|
| ECS Cluster | `pmm-agent-dev` / `pmm-agent-prod` | Runs orchestration service |
| ECS Service | `pmm-orchestration` | Single service, 1 task (dev) / 2 tasks (prod) |
| ECR Repository | `pmm-orchestration` | Container images |
| ElastiCache | `pmm-agent-redis-dev` | Session state, eGain tokens |
| S3 (context) | `egain-pmm-agent-context-{account_id}` | company-context.md |
| S3 (frontend) | `egain-pmm-agent-ui-{account_id}` | Static chat widget |
| CloudFront | per environment | HTTPS for frontend |
| Secrets Manager | `pmm-agent/aha-api-key` | Aha Basic auth key |
| Secrets Manager | `pmm-agent/egain-credentials` | eGain client_app + client_secret (on-behalf-of-customer auth) |
| Secrets Manager | `pmm-agent/gemini-api-key` | Gemini API key (default provider) |
| Secrets Manager | `pmm-agent/anthropic-api-key` | Anthropic API key |
| Secrets Manager | `pmm-agent/openai-api-key` | OpenAI API key |
| DynamoDB | `pmm-agent-sessions` | Session history — written once at session end (PK: session_id) |
| Lambda | `pmm-skill-client` | Generic skill executor — reads api_config dict from payload, authenticates per auth.type, makes API call |
| Lambda | `pmm-context-refresher` | Invalidates s3_loader cache on context update |

---

## Secrets Manager Secret Shapes

```json
// pmm-agent/aha-api-key
{"api_key": "..."}

// pmm-agent/egain-credentials (on-behalf-of-customer auth)
{"client_app": "...", "client_secret": "..."}

// pmm-agent/gemini-api-key (default LLM provider)
{"api_key": "..."}

// pmm-agent/anthropic-api-key
{"api_key": "..."}

// pmm-agent/openai-api-key
{"api_key": "..."}
```

---

## Adding a New Integration (Extension Pattern)

To add, e.g., Jira:

```
1. Create  config/skills/jira/SKILL.md           ← when/how to use Jira tools
2. Create  config/skills/jira/tools.py           ← Python tool functions + JIRA_API_CONFIG constant
3. Create  config/skills/jira/scripts/jira_client.py  ← JiraClient class
4. Create  config/skills/jira/references/api.md  ← field paths, status values
5. Edit    services/orchestration/tools/deps.py  ← add JiraClient to AgentDeps + build_deps()
6. Import  JIRA_TOOLS from config/skills/jira/tools.py in the relevant node file
7. Add     jira_skill=_get_skill_md("jira") to AgentDeps

No graph changes. No new service. No new Dockerfile. No Terraform changes.
```

---

## Common File Relationships (quick reference)

| When you edit... | Also check / update... |
|---|---|
| `config/skills/aha/tools.py` | `config/skills/aha/SKILL.md` (instruction may need updating), `release_context_agent.py` (imports AHA_TOOLS) |
| `config/skills/aha/SKILL.md` | `services/orchestration/graph/nodes/release_context_agent.py` (@agent.instructions) |
| `config/skills/aha/scripts/aha_client.py` | `services/orchestration/tools/deps.py` (uses AhaClient), `tests/unit/tools/test_aha_client.py` |
| `context/company-context.md` | `config/skills/company-context/SKILL.md` (parsing rules), `tests/fixtures/mock_company_context.md` |
| `services/orchestration/session/models.py` | `services/orchestration/context_loader/s3_loader.py` (produces PMContext), `tests/unit/orchestration/test_models.py` |
| `services/orchestration/tools/deps.py` | Every graph node file (all use AgentDeps), `tests/unit/orchestration/test_api_endpoints.py` |
| `.github/workflows/ci-dev.yml` | `.github/workflows/deploy-prod.yml` (keep ECS commands in sync) |
| `docs/pmm-ai-agent-guide.md` | This file (`REPO.md`) — keep section numbers + step names in sync when guide changes |
| Any `graph/nodes/*.py` | `graph/graph.py` Graph(nodes=[...]) list (must include every node class) |
