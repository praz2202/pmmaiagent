# PMM AI Agent — Architecture Diagrams

**Version:** 3.0
**Last updated:** March 2026
**Related docs:** `REPO.md` · `pmm-ai-agent-implementation-guide.md`

All diagrams use Mermaid. Render in GitHub, VS Code (Mermaid extension), or any Mermaid-compatible viewer.

---

## 1. System Overview

High-level picture of all components, data flow, and external integrations.

```mermaid
graph TD
    PM["PM\n(Product Manager)"]

    subgraph Frontend["Frontend — GitHub Pages"]
        UI["dev.controlflows.com\nMSAL SSO login\nChat UI + New Chat button\nSSE streaming"]
    end

    subgraph EC2["EC2 t3.small — Docker Compose"]
        Nginx["Nginx\nLet's Encrypt HTTPS\napi.controlflows.com\nreverse proxy → :8000"]
        API["FastAPI\n/pm/resolve\n/sessions/start\n/sessions/{id}/respond (SSE)\n/sessions/{id}/end\n/health"]
        Agent["PydanticAI Agent\nSingle agent with tools\nDynamic skill loading\nContext tools on demand"]
        APIClient["api_client.py\naha_api_call()\negain_api_call()\nDirect httpx — no Lambda"]
        RedisC["Redis Container\nSession state\nConversation history"]
    end

    subgraph AWS["AWS"]
        DDB["DynamoDB\npmm-agent-sessions\n(session history,\nwritten at session end)"]
    end

    subgraph Observability["Observability"]
        Logfire["Logfire\nFastAPI instrumented\nhttpx instrumented\nPydanticAI instrumented"]
    end

    subgraph External["External APIs"]
        Aha["Aha API\negain.aha.io/api/v1\nBearer token auth"]
        eGain["eGain Knowledge API v4\napi.egain.cloud\nOBO token auth\nRead-only"]
    end

    PM -->|"HTTPS"| UI
    UI -->|"REST + SSE"| Nginx
    Nginx -->|"proxy_pass :8000"| API
    API --> Agent
    Agent --> APIClient
    APIClient -->|"httpx — Bearer token"| Aha
    APIClient -->|"httpx — OBO token"| eGain
    Agent <-->|"session state"| RedisC
    API -->|"write session record\n(at session end)"| DDB
    API --> Logfire
    APIClient --> Logfire

    style EC2 fill:#FDF2F8,stroke:#DB2777
    style Frontend fill:#EFF6FF,stroke:#2563EB
    style AWS fill:#F0FDF4,stroke:#16A34A
    style External fill:#FFFBEB,stroke:#D97706
    style Observability fill:#F5F3FF,stroke:#7C3AED
```

---

## 2. Agent Tool Architecture

Single PydanticAI Agent with dynamic skill loading and context tools.

```mermaid
graph TD
    subgraph AgentCore["PydanticAI Agent"]
        SysPrompt["System Prompt\nMinimal — skill index only\nLoaded at agent init"]
        SkillLoader["load_skill() tool\nDynamic skill loading\nPM says 'release features'\n→ loads release_features skill"]
        CtxTools["Context Tools\n(loaded on demand)"]
    end

    subgraph Skills["skills/ — 5 skill folders"]
        RF["release_features/\nTools: search releases,\nget features by release,\nget feature details"]
        FS["feature_search/\nTools: search features\nacross products"]
        RN["release_notes/\nKnowledge only — no tools\nRules for writing release notes"]
        PA["portal_articles/\nTools: search articles,\nget article content,\nlist topics"]
        CTX["context/\nRules and references\nfor PM context"]
    end

    subgraph ContextTools["Context Tools (on demand)"]
        RT["get_release_tracking\nRelease tracking rules\nand conventions"]
        PS["get_portal_structure\nPortal folder/topic\nhierarchy"]
        DR["get_document_rules\nDocument formatting\nand style rules"]
    end

    subgraph APILayer["api_client.py"]
        AhaCall["aha_api_call()\nhttpx + Bearer token\nDirect to Aha API"]
        eGainCall["egain_api_call()\nhttpx + OBO token\nDirect to eGain API"]
    end

    SkillLoader -->|"loads tools + instructions"| RF
    SkillLoader -->|"loads tools + instructions"| FS
    SkillLoader -->|"loads knowledge"| RN
    SkillLoader -->|"loads tools + instructions"| PA
    SkillLoader -->|"loads rules"| CTX

    CtxTools --> RT
    CtxTools --> PS
    CtxTools --> DR

    RF --> AhaCall
    FS --> AhaCall
    PA --> eGainCall

    style AgentCore fill:#FDF2F8,stroke:#DB2777
    style Skills fill:#F0FDF4,stroke:#16A34A
    style ContextTools fill:#EFF6FF,stroke:#2563EB
    style APILayer fill:#FFFBEB,stroke:#D97706
```

---

## 3. Session Lifecycle

Sequence diagram showing the full lifecycle of a PM session from login to end.

```mermaid
sequenceDiagram
    participant PM as PM (browser)
    participant FE as Frontend<br/>dev.controlflows.com
    participant API as FastAPI<br/>api.controlflows.com
    participant Agent as PydanticAI Agent
    participant Redis as Redis (Docker)
    participant DDB as DynamoDB
    participant Aha as Aha API
    participant eGain as eGain API

    Note over PM,eGain: Step 1 — PM signs in via MSAL

    PM->>FE: Opens dev.controlflows.com
    FE->>FE: MSAL SSO login (Azure AD)
    FE-->>PM: Authenticated — chat UI shown

    Note over PM,eGain: Step 2 — Resolve PM and start session

    FE->>API: POST /pm/resolve {email}
    API-->>FE: {pm_name, products, permissions}

    FE->>API: POST /sessions/start {pm_name}
    API->>Agent: Initialize agent with PM context
    Agent-->>API: Greeting message
    API->>Redis: Store session state
    API-->>FE: {session_id, message: "Hi! How can I help?"}
    FE-->>PM: Agent greeting displayed

    Note over PM,eGain: Step 3 — Conversation turns (SSE streaming)

    PM->>FE: Types message
    FE->>API: POST /sessions/{id}/respond {input} (SSE)
    API->>Redis: Load session state
    API->>Agent: Run agent with PM input

    Agent->>Agent: load_skill("release_features")
    Agent->>Aha: aha_api_call() — httpx direct
    Aha-->>Agent: Feature data
    Agent->>eGain: egain_api_call() — httpx direct
    eGain-->>Agent: Article data

    Agent-->>API: Streamed response tokens
    API->>Redis: Update session state
    API-->>FE: SSE stream: text chunks
    FE-->>PM: Response rendered incrementally

    Note over PM,eGain: Repeat Step 3 for each conversation turn

    Note over PM,eGain: Step 4 — PM clicks New Chat

    PM->>FE: Clicks "New Chat"
    FE->>API: POST /sessions/{id}/end
    API->>Redis: Load final session state
    API->>DDB: Write SessionRecord (full history)
    API->>Redis: Delete session state
    API-->>FE: {ended: true}
    FE-->>PM: Chat UI reset — ready for new session
```

---

## 4. Auth Flow

How authentication works for each component in the system.

```mermaid
sequenceDiagram
    participant PM as PM (browser)
    participant FE as Frontend
    participant AAD as Azure AD
    participant API as FastAPI
    participant Agent as PydanticAI Agent
    participant AhaAPI as Aha API
    participant eGainAPI as eGain API

    Note over PM,eGainAPI: Frontend Auth — MSAL SSO

    PM->>FE: Opens dev.controlflows.com
    FE->>AAD: MSAL redirect (client_id, scopes)
    AAD->>PM: Azure AD login prompt
    PM->>AAD: Credentials
    AAD-->>FE: ID token + access token
    FE->>FE: Store token in session
    FE->>API: All requests include Authorization header

    Note over PM,eGainAPI: Aha API Auth — Bearer Token

    Agent->>Agent: Tool call requires Aha data
    Agent->>AhaAPI: GET /api/v1/products/{key}/features
    Note over Agent,AhaAPI: Authorization: Bearer {aha_token}<br/>Token loaded from environment/config at startup

    AhaAPI-->>Agent: JSON response (features, releases, etc.)

    Note over PM,eGainAPI: eGain API Auth — On-Behalf-Of (OBO) Token

    Agent->>Agent: Tool call requires eGain data
    Agent->>eGainAPI: GET /system/v4/kb/articles
    Note over Agent,eGainAPI: x-egain-session header with OBO token<br/>Token obtained via eGain auth endpoint<br/>Read-only access

    eGainAPI-->>Agent: JSON response (articles, topics, etc.)

    Note over PM,eGainAPI: Key principle: LLM never sees credentials.<br/>api_client.py handles all auth headers.<br/>Agent only sees tool return values.
```

---

## 5. Deployment Architecture

EC2 instance with Docker Compose, Nginx reverse proxy, and supporting services.

```mermaid
graph TD
    Internet(["Internet\n(PM browser)"])

    subgraph GHPages["GitHub Pages"]
        FE["dev.controlflows.com\nStatic frontend\nMSAL SSO\nChat UI"]
    end

    subgraph EC2["EC2 t3.small"]

        subgraph DockerCompose["Docker Compose"]

            subgraph NginxC["Nginx Container"]
                Nginx["Nginx\napi.controlflows.com\nLet's Encrypt TLS\nreverse proxy → app:8000"]
            end

            subgraph AppC["App Container"]
                FastAPI["FastAPI\nPydanticAI Agent\napi_client.py (httpx)\nLogfire instrumented\nPort 8000"]
            end

            subgraph RedisC["Redis Container"]
                Redis["Redis\nSession state\nPort 6379\nLocal persistence"]
            end
        end
    end

    subgraph AWS["AWS Services"]
        DDB["DynamoDB\npmm-agent-sessions\nSession history"]
    end

    subgraph External["External APIs"]
        Aha["Aha API\negain.aha.io"]
        eGain["eGain API\napi.egain.cloud"]
    end

    subgraph Monitoring["Observability"]
        Logfire["Logfire\nTraces + metrics\nFastAPI spans\nhttpx spans\nPydanticAI spans"]
    end

    Internet -->|"HTTPS"| FE
    Internet -->|"HTTPS :443"| Nginx
    Nginx -->|"HTTP :8000"| FastAPI
    FastAPI <-->|":6379"| Redis
    FastAPI -->|"HTTPS"| Aha
    FastAPI -->|"HTTPS"| eGain
    FastAPI -->|"PutItem"| DDB
    FastAPI -->|"traces"| Logfire

    style EC2 fill:#FDF2F8,stroke:#DB2777,stroke-width:2px
    style DockerCompose fill:#FCE7F3,stroke:#EC4899
    style GHPages fill:#EFF6FF,stroke:#2563EB
    style AWS fill:#F0FDF4,stroke:#16A34A
    style External fill:#FFFBEB,stroke:#D97706
    style Monitoring fill:#F5F3FF,stroke:#7C3AED
```

---

## Diagram Index

| # | Diagram | What it shows |
|---|---|---|
| 1 | System Overview | All components: GitHub Pages frontend, EC2 + Docker backend, direct API calls to Aha/eGain, Redis, DynamoDB, Logfire |
| 2 | Agent Tool Architecture | Single PydanticAI Agent with dynamic skill loading (5 skill folders), context tools, and direct httpx API client |
| 3 | Session Lifecycle | Full sequence: MSAL login, /pm/resolve, /sessions/start, SSE streaming via /sessions/{id}/respond, /sessions/{id}/end |
| 4 | Auth Flow | MSAL SSO for frontend, Bearer token for Aha, OBO token for eGain — LLM never sees credentials |
| 5 | Deployment Architecture | EC2 t3.small with Docker Compose (Nginx + App + Redis), Nginx + Let's Encrypt for HTTPS |
