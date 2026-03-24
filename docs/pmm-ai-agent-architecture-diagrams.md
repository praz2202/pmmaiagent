# PMM AI Agent — Architecture Diagrams

**Version:** 2.0  
**Last updated:** March 2026  
**Related docs:** `REPO.md` · `pmm-ai-agent-implementation-guide.md`

All diagrams use Mermaid. Render in GitHub, VS Code (Mermaid extension), or any Mermaid-compatible viewer.

---

## 1. System Overview

High-level picture of all components, who calls what, and where data lives.

```mermaid
graph TD
    PM["👤 PM\n(Aiushe, Prasanth, Carlos,\nAnkur, Peter, Kevin, Varsha)"]

    subgraph Frontend["Frontend — S3 + CloudFront"]
        UI["index.html\nPM dropdown (4 PMs)\nChat widget + Restart button\nSSE heartbeats"]
    end

    subgraph Service["ECS Fargate — pmm-orchestration"]
        API["FastAPI\n/sessions/*\n/health\n/internal/*"]
        Graph["PydanticAI Graph\n21 BaseNode classes\n6 HITL gates\nGraph.iter() for HITL"]
        ToolMods["Tool Modules\ntools.py per skill\nimported by agent nodes"]
        Deps["AgentDeps\nLambdaClient (boto3)\nPMContext + skill strings"]
    end

    subgraph Skills["config/skills/ — in repo"]
        AhaSkill["aha/\nSKILL.md\ntools.py (5 tools)\nreferences/api.md"]
        EgainSkill["egain/\nSKILL.md\ntools.py (2 read-only)\nreferences/api.md"]
        CtxSkill["company-context/\nSKILL.md\nreferences/parsing.md"]
    end

    subgraph AWS["AWS"]
        Redis["ElastiCache Redis\nsession:{id} — 24h TTL\n(live session state)"]
        DDB["DynamoDB\npmm-agent-sessions\n(session history,\nwritten at end)"]
        S3ctx["S3 — context bucket\ncompany-context.md\n(versioned, encrypted)"]
        S3ui["S3 + CloudFront\nfrontend static files"]
        SM["Secrets Manager\naha-api-key\negain-credentials\ngemini-api-key (default)\nanthropic-api-key\nopenai-api-key"]
        LambdaSkill["Lambda\npmm-skill-client\n(generic skill executor)"]
        LambdaCtx["Lambda\ncontext-refresher\n(S3 trigger)"]
    end

    subgraph External["External APIs"]
        Aha["Aha\negain.aha.io/api/v1\nBasic auth\n100 req/min"]
        Portal["eGain Knowledge API v4\napi.egain.cloud\nOn-behalf-of-customer auth\nRead-only"]
    end

    PM -->|"HTTPS chat"| UI
    UI -->|"REST + SSE"| API
    API --> Graph
    Graph --> Deps
    Deps -->|"reads at startup"| Skills
    ToolMods -->|"imports from tools.py"| Skills
    Deps -->|"invoke with API_CONFIG"| LambdaSkill
    LambdaSkill -->|"Basic auth (from API_CONFIG)"| Aha
    LambdaSkill -->|"on-behalf-of-customer\n(read-only)"| Portal
    LambdaSkill -->|"get credentials"| SM
    Deps -->|"load PMContext"| S3ctx
    Deps -->|"get LLM API key\n(default: Gemini)"| SM
    Graph -->|"save/load state"| Redis
    Graph -->|"write session record\n(at session end)"| DDB
    LambdaCtx -->|"S3 event → invalidate cache"| API
    UI -.->|"served from"| S3ui

    style Service fill:#FDF2F8,stroke:#DB2777
    style Skills fill:#F0FDF4,stroke:#16A34A
    style AWS fill:#EFF6FF,stroke:#2563EB
    style External fill:#FFFBEB,stroke:#D97706
```

---

## 2. PydanticAI Graph — Full Node Flow

Complete state machine showing every node, HITL gates, and routing decisions.

```mermaid
flowchart TD
    START(["Session Start\nPOST /sessions/start"]) --> Entry

    Entry["EntryNode\nGreet PM, detect intent"]

    Entry -->|"release intent"| CtxSetup
    Entry -->|"specific article"| AdHoc
    Entry -->|"unclear"| Entry

    CtxSetup["ContextSetupNode\n⚙️ Python logic\nValidate PMContext"]
    CtxSetup --> RelConfirm

    RelConfirm{{"ReleaseConfirmNode\n★ HITL Gate 1\nList releases → PM picks"}}
    RelConfirm -->|"AIA: shows AIA x.x.x tags"| RelConfirm
    RelConfirm -->|"confirmed"| RelCtx

    RelCtx["ReleaseContextAgentNode\n🔧 Tool-Agent Node\nAha tools: 1–3 Lambda calls\nfull features + attachments"]
    RelCtx --> PortalCtx

    PortalCtx["PortalContextAgentNode\n🔧 Tool-Agent Node\neGain read-only tools:\ngetarticlesintopic, getarticlebyid"]
    PortalCtx --> PlanGen

    PlanGen["PlanGenNode\n🧠 LLM Reasoning\nMatch features → articles\nPropose updates + creates"]
    PlanGen --> PlanReview

    PlanReview{{"PlanReviewNode\n★ HITL Gate 2\nPresent full plan to PM"}}
    PlanReview -->|"edit + feedback"| PlanGen
    PlanReview -->|"confirmed"| ModeSelect

    ModeSelect{{"ModeSelectNode\n★ HITL Gate 3\n⚙️ Python logic\nKeyword match on PM input"}}
    ModeSelect -->|"updates first"| ShowUpdate
    ModeSelect -->|"creates first"| ShowCreate

    subgraph UpdateLoop["Update Iterator — per article"]
        ShowUpdate["ShowUpdatePlan\n⚙️ Python formatting\nShow title + planned changes"]
        UpdateFB{{"UpdateFeedbackGate\n★ HITL per article"}}
        RefineUpd["RefineUpdate\nLLM refines based on feedback"]
        AdvUpdate["AdvanceUpdate\n⚙️ Python logic\nMove to next article"]

        ShowUpdate --> UpdateFB
        UpdateFB -->|"feedback"| RefineUpd
        RefineUpd --> ShowUpdate
        UpdateFB -->|"confirmed"| AdvUpdate
        AdvUpdate -->|"more articles"| ShowUpdate
    end

    subgraph CreateLoop["Create Iterator — per article"]
        ShowCreate["ShowCreatePlan\n⚙️ Python formatting\nShow title + folder + outline"]
        CreateFB{{"CreateFeedbackGate\n★ HITL per article"}}
        RefineCreate["RefineCreate\nLLM refines based on feedback"]
        AdvCreate["AdvanceCreate\n⚙️ Python logic\nMove to next article"]

        ShowCreate --> CreateFB
        CreateFB -->|"feedback"| RefineCreate
        RefineCreate --> ShowCreate
        CreateFB -->|"confirmed"| AdvCreate
        AdvCreate -->|"more articles"| ShowCreate
    end

    AdvUpdate -->|"updates done\nif creates remain"| ShowCreate
    AdvCreate -->|"creates done\nif updates remain"| ShowUpdate
    AdvUpdate -->|"all done"| Output
    AdvCreate -->|"all done"| Output

    subgraph AdHocFlow["Ad-hoc Flow"]
        AdHoc["AdHocRouterNode\n★ HITL\nKnows article or suggest?"]
        AskArt["AskArticleNode\nCollect article ID or folder"]
        Suggest["SuggestNode\nSearch portal\nPresent best match"]

        AdHoc -->|"knows it"| AskArt
        AdHoc -->|"suggest me"| Suggest
        Suggest -->|"rejected"| Suggest
        Suggest -->|"accepted"| ShowUpdate
        AskArt -->|"update"| ShowUpdate
        AskArt -->|"create"| ShowCreate
    end

    Output["OutputAgentNode\n🧠 LLM Reasoning\nPresent HTML content to PM\nSuggest create / update / both"]
    Output --> OutputReview

    OutputReview{{"OutputReviewNode\n★ HITL Gate 6\nPM reviews final HTML output"}}
    OutputReview -->|"approved"| Done
    OutputReview -->|"feedback"| Output

    Done(["DoneNode\n⚙️ Python logic\nReturns End — session complete"])

    style RelConfirm fill:#FEF3C7,stroke:#D97706
    style PlanReview fill:#FEF3C7,stroke:#D97706
    style ModeSelect fill:#FEF3C7,stroke:#D97706
    style UpdateFB fill:#FEF3C7,stroke:#D97706
    style CreateFB fill:#FEF3C7,stroke:#D97706
    style AdHoc fill:#FEF3C7,stroke:#D97706
    style OutputReview fill:#FEF3C7,stroke:#D97706
    style RelCtx fill:#FDF2F8,stroke:#DB2777
    style PortalCtx fill:#FDF2F8,stroke:#DB2777
    style Output fill:#EFF6FF,stroke:#2563EB
    style CtxSetup fill:#F0FDF4,stroke:#16A34A
    style AdvUpdate fill:#F0FDF4,stroke:#16A34A
    style AdvCreate fill:#F0FDF4,stroke:#16A34A
```

---

## 3. Skill Folder Architecture

How the Anthropic skills standard maps to this project.

```mermaid
graph TD
    subgraph SkillsDir["config/skills/ — one folder per integration"]

        subgraph AhaSkill["aha/"]
            AhaSKILL["SKILL.md\nLLM instructions:\n• AIA vs standard routing\n• call order\n• cross-product rules"]
            AhaTools["tools.py\nPython tool functions:\n• AHA_TOOLS list\n• API_CONFIG dict\n• endpoint + params\n• response_path + filters"]
            AhaTools["tools.py\n5 tool functions\nAHA_API_CONFIG + AHA_TOOLS"]
            AhaRef["references/api.md\nAha field paths\nrate limit rules\nrelease name formats\n(lazy loaded)"]
        end

        subgraph EgainSkill["egain/"]
            EgainSKILL["SKILL.md\nLLM instructions:\n• read API usage\n• suggest create vs update\n• HTML content format"]
            EgainTools["tools.py\n2 read-only tools:\n• getarticlesintopic\n• getarticlebyid\n• EGAIN_TOOLS list"]
            EgainRef["references/api.md\neGain Knowledge API v4\narticle structure\nHTML format\n(lazy loaded)"]
        end

        subgraph CtxSkill["company-context/"]
            CtxSKILL["SKILL.md\nLLM instructions:\n• PMContext fields\n• release type rules\n• cross-product flags"]
            CtxRef["references/parsing.md\nMarkdown table format\nfield extraction patterns"]
        end
    end

    subgraph Loaders["services/orchestration/"]
        SkillLoader["context_loader/skill_loader.py\nloads SKILL.md\nlru_cache indefinitely"]
        Deps["tools/deps.py\nAgentDeps dataclass\nbuild_deps() factory\nLambdaClient (boto3)"]
    end

    subgraph Nodes["graph/nodes/"]
        RCA["release_context_agent.py\nAgent(..., tools=AHA_TOOLS)\nimports from aha/tools.py\ninjects aha_skill"]
        PCA["portal_context_agent.py\nAgent(..., tools=EGAIN_TOOLS)\nimports from egain/tools.py\ninjects egain_skill"]
        OA["output_agent.py\n@agent.instructions\nLLM reasoning: present HTML\nsuggest create/update/both"]
    end

    AhaTools -->|"from aha.tools import AHA_TOOLS"| RCA
    EgainTools -->|"from egain.tools import EGAIN_TOOLS"| PCA
    AhaSKILL -->|"load_skill_md('aha')"| SkillLoader
    EgainSKILL -->|"load_skill_md('egain')"| SkillLoader
    AhaClient -->|"optional helpers"| Deps
    SkillLoader -->|"AgentDeps.aha_skill"| Deps
    SkillLoader -->|"AgentDeps.egain_skill"| Deps

    Deps -->|"injected via RunContext"| RCA
    Deps -->|"injected via RunContext"| PCA
    Deps -->|"injected via RunContext"| OA

    style AhaSkill fill:#FFFBEB,stroke:#D97706
    style EgainSkill fill:#F0FDF4,stroke:#16A34A
    style CtxSkill fill:#EFF6FF,stroke:#2563EB
    style Loaders fill:#FDF2F8,stroke:#DB2777
    style Nodes fill:#F9FAFB,stroke:#6B7280
```

---

## 4. Concurrent Session Model

How multiple PMs can use the service simultaneously with full isolation. Skill scripts run as stateless Lambdas — no process-level singletons.

```mermaid
graph TD
    subgraph Process["ECS Container — single process"]
        CtxCache["Company Context Cache\n★ PROCESS LEVEL\n5-min TTL dict\nAll sessions share one parse"]
        SkillCache["Skill MD Cache\n★ PROCESS LEVEL\nlru_cache indefinitely\nChanged only on deploy"]
        LambdaC["LambdaClient\n★ PROCESS LEVEL\nboto3 Lambda invoker\nstateless, shared"]

        subgraph Session1["Session A — Prasanth (AIA + ECAI)"]
            Deps1["AgentDeps A\nlambda_client → shared ↑\nsession_id: session-A\npm_context → parsed slice\nrelease_label: 'AIA 1.2.0'"]
        end

        subgraph Session2["Session B — Aiushe (AIA)"]
            Deps2["AgentDeps B\nlambda_client → shared ↑\nsession_id: session-B\npm_context → parsed slice\nrelease_label: 'AIA 1.2.0'"]
        end

        subgraph Session3["Session C — Carlos (ECAI)"]
            Deps3["AgentDeps C\nlambda_client → shared ↑\nsession_id: session-C\npm_context → parsed slice\nrelease_label: '25.03'"]
        end
    end

    subgraph Lambdas["Skill Lambda — stateless, config-driven"]
        SkillLambda["pmm-skill-client\nGeneric skill executor\nReads API_CONFIG from payload\nauth.type=basic → Secrets Manager\nauth.type=basic_onbehalf → Secrets Manager\nFresh httpx client per invocation"]
    end

    subgraph Redis["ElastiCache Redis"]
        StateA["session:session-A\nPMAgentState (no creds)"]
        StateB["session:session-B\nPMAgentState (no creds)"]
        StateC["session:session-C\nPMAgentState (no creds)"]
    end

    LambdaC -->|"invoke with API_CONFIG"| SkillLambda
    SkillLambda -->|"get credentials"| SM2
    SM2["Secrets Manager"]
    Deps1 <-->|"save / load state"| StateA
    Deps2 <-->|"save / load state"| StateB
    Deps3 <-->|"save / load state"| StateC

    style Process fill:#F9FAFB,stroke:#D1D5DB
    style Session1 fill:#FDF2F8,stroke:#DB2777
    style Session2 fill:#FDF2F8,stroke:#DB2777
    style Session3 fill:#FDF2F8,stroke:#DB2777
    style Lambdas fill:#F0FDF4,stroke:#16A34A
    style Redis fill:#EFF6FF,stroke:#2563EB
```

---

## 5. Auth and Credential Flow

How credentials travel from AWS Secrets Manager into API calls — and what the LLM never sees.

```mermaid
sequenceDiagram
    participant SM as Secrets Manager
    participant Deps as build_deps()
    participant AgentDeps as AgentDeps
    participant Node as Agent Node
    participant LLM as Claude LLM
    participant Tool as tool_fn(ctx)
    participant Lambda as pmm-skill-client Lambda
    participant AhaAPI as Aha API

    Note over SM,AhaAPI: Session start — no credential resolution needed

    Deps->>Deps: LambdaClient(boto3.client("lambda"))
    Deps->>SM: get_secret_value(PROVIDERS[DEFAULT_PROVIDER].credentials_secret)
    SM-->>Deps: {"api_key": "..."}
    Deps->>Deps: OpenAIModel(model, openai_client=AsyncOpenAI(base_url, api_key))
    Deps-->>AgentDeps: {lambda_client, llm_model, model_settings, pm_context, session_id, skills}
    Note over Deps: Only LLM API key loaded — skill Lambdas fetch their own credentials

    Note over AgentDeps,AhaAPI: Tool call during agent run

    Node->>LLM: agent.run(prompt, deps=AgentDeps)
    Note over LLM: LLM sees: tool descriptions from SKILL.md<br/>LLM sees: @agent.instructions (pm_context fields, skill text)<br/>LLM NEVER sees: API keys, base URLs, auth headers

    LLM->>Tool: aha_get_release_features(product_key="AIA", tag="AIA 1.2.0")
    Tool->>AgentDeps: ctx.deps.lambda_client
    Tool->>Lambda: lambda.invoke(pmm-skill-client, {payload + API_CONFIG})
    Note over Lambda: Reads API_CONFIG.auth.type = "basic"<br/>API_CONFIG.auth.credentials_secret = "pmm-agent/aha-api-key"
    Lambda->>SM: get_secret_value("pmm-agent/aha-api-key")
    SM-->>Lambda: {"api_key": "sk-..."}
    Lambda->>Lambda: httpx.Client + Basic auth header (from API_CONFIG)
    Lambda->>AhaAPI: GET /products/AIA/features?tag=AIA+1.2.0&fields=name,description,custom_fields,tags,attachments
    AhaAPI-->>Lambda: [{id, name, description, custom_fields, tags, attachments}, ...]
    Lambda-->>Tool: [full feature objects with all details]
    Tool-->>LLM: [full feature objects with all details]

    Note over LLM: LLM sees only the return value — tool result
    Note over SM,AhaAPI: Credentials never leave the Lambda — orchestration service has zero access
```

---

## 6. HITL Session Lifecycle

How a multi-turn conversation persists across HTTP requests.

```mermaid
sequenceDiagram
    participant PM as PM (browser)
    participant API as FastAPI
    participant Graph as PydanticAI Graph
    participant Redis as Redis
    participant Aha as Aha API
    participant Portal as eGain Portal

    Note over PM,Portal: PM selects name from dropdown (Prasanth, Aiushe, Carlos, Varsha)

    PM->>API: POST /sessions/start\n{pm_name:"Prasanth Sai", mode:"release"}

    API->>API: map pm_name → pm_email via company-context.md
    API->>API: load_company_context(pm_email) → PMContext
    API->>API: build_deps(pm_context, session_id) → AgentDeps (LambdaClient, no API creds)
    API->>Graph: run EntryNode
    Graph-->>API: {message:"Hi Prasanth! Which release?", next_node:"ReleaseConfirmNode"}
    API->>Redis: SETEX session:{id} 86400 {state}
    API-->>PM: {session_id, message, awaiting_input:true}

    Note over PM,Portal: PM reads the list of releases, picks one

    PM->>API: POST /sessions/{id}/respond\n{input:"AIA 1.2.0"}
    API->>Redis: GET session:{id} → PMAgentState
    API->>API: build_deps(state.pm_context, session_id) → AgentDeps
    Note over API: No client objects — Lambdas handle auth
    API->>Graph: resume ReleaseConfirmNode with pm_input="AIA 1.2.0"
    Graph->>Aha: Lambda: aha_get_release_features(product_key="AIA", tag="AIA 1.2.0", fields=all)
    Graph->>Portal: Lambda: egain_get_articles_in_topic(portal_id, topic_id) × N topics
    Graph->>Graph: PlanGenNode — LLM generates DocumentPlan
    Graph-->>API: {message:"Here is my plan...", plan:{...}, next_node:"PlanReviewNode"}
    API->>Redis: SETEX session:{id} 86400 {updated state with plan}
    API-->>PM: {message, plan, awaiting_input:true}

    Note over PM,Portal: PM reviews plan, confirms

    PM->>API: POST /sessions/{id}/respond\n{input:"looks good"}
    API->>Redis: GET session:{id}
    API->>Graph: resume PlanReviewNode
    Graph-->>API: {next_node:"ModeSelectNode"}

    Note over PM,Portal: ... HITL gates 3, 4, 5 follow same pattern ...

    PM->>API: POST /sessions/{id}/respond\n{input:"confirm"} (last article)
    API->>Graph: resume UpdateFeedbackGate → OutputAgentNode
    Graph->>Graph: LLM generates HTML content for each confirmed article
    Graph->>Graph: LLM recommends: create new / update existing / both options
    Graph-->>API: {message:"Here is the content...", articles:[{html, recommendation}]}
    API->>Redis: SETEX session:{id} 86400 {final state}
    API-->>PM: {message, articles with HTML + create/update recommendations}

    Note over PM,Portal: Session complete — or PM clicks Restart

    PM->>API: POST /sessions/{id}/end\n{reason:"completed"|"restarted"}
    API->>Redis: GET session:{id} → final PMAgentState
    API->>API: build SessionRecord from state\n(tool_calls with result="tool response received")
    API->>Redis: DELETE session:{id}
    Note over API: DynamoDB write
    API-->>PM: {ended: true}

    Note over PM,Portal: If restarted: widget returns to PM dropdown → new session
```

---

## 7. AWS Infrastructure

Network topology and resource placement.

```mermaid
graph TD
    Internet(["Internet\n(PM browser)"])

    subgraph VPC["AWS VPC — 10.0.0.0/16"]

        subgraph PublicSubnets["Public Subnets (2 AZs)"]
            ALB["Application Load Balancer\nHTTPS → :8000\nroutes to ECS tasks"]
        end

        subgraph PrivateSubnets["Private Subnets (2 AZs)"]
            subgraph ECS["ECS Fargate Cluster"]
                Task1["pmm-orchestration\ntask 1\n1 vCPU / 2 GB"]
                Task2["pmm-orchestration\ntask 2 (prod only)\n1 vCPU / 2 GB"]
            end

            Redis["ElastiCache Redis\ncache.t4g.small\nno public access\nport 6379\n(live session state)"]
        end

        subgraph SGs["Security Groups"]
            SGalb["sg-alb\ninbound: 443 from 0.0.0.0/0"]
            SGorch["sg-orchestration\ninbound: 8000 from sg-alb only\noutbound: 6379 to sg-redis\noutbound: 443 to 0.0.0.0/0"]
            SGredis["sg-redis\ninbound: 6379 from sg-orchestration only"]
        end
    end

    subgraph AWSServices["AWS Services (no VPC)"]
        ECR["ECR\npmm-orchestration\ncontainer images"]
        S3ctx["S3\negain-pmm-agent-context-{id}\ncompany-context.md"]
        S3ui["S3 + CloudFront\negain-pmm-agent-ui-{id}\nstatic frontend"]
        SM["Secrets Manager\npmm-agent/aha-api-key\npmm-agent/egain-credentials\npmm-agent/gemini-api-key\npmm-agent/anthropic-api-key\npmm-agent/openai-api-key"]
        LambdaCtx["Lambda\ncontext-refresher"]
        DDB["DynamoDB\npmm-agent-sessions\n(session history)"]
        LambdaSkill["Lambda\npmm-skill-client\n(generic skill executor)"]
        CW["CloudWatch Logs\n/ecs/pmm-orchestration\n/lambda/pmm-skill-client"]
    end

    subgraph External["External APIs"]
        Aha["egain.aha.io\nBasic auth"]
        Portal["api.egain.cloud\nKnowledge API v4\nOn-behalf-of-customer\nRead-only"]
    end

    Internet -->|"HTTPS"| ALB
    ALB --> Task1
    ALB --> Task2
    Task1 <-->|"6379"| Redis
    Task2 <-->|"6379"| Redis
    Task1 -->|"pull image"| ECR
    Task1 -->|"GetObject"| S3ctx
    Task1 -->|"GetSecretValue"| SM
    Task1 -->|"PutLogEvents"| CW
    Task1 -->|"PutItem (session end)"| DDB
    Task1 -->|"lambda:Invoke"| LambdaSkill
    LambdaSkill -->|"HTTPS 443"| Aha
    LambdaSkill -->|"HTTPS 443\n(read-only)"| Portal
    LambdaSkill -->|"GetSecretValue"| SM
    S3ctx -->|"ObjectCreated event"| LambdaCtx
    LambdaCtx -->|"POST /internal/context/invalidate"| ALB

    Internet -->|"HTTPS"| S3ui

    style VPC fill:#EFF6FF,stroke:#2563EB,stroke-width:2px
    style PublicSubnets fill:#DBEAFE,stroke:#3B82F6
    style PrivateSubnets fill:#E0F2FE,stroke:#0284C7
    style ECS fill:#FDF2F8,stroke:#DB2777
    style AWSServices fill:#F0FDF4,stroke:#16A34A
    style External fill:#FFFBEB,stroke:#D97706
```

---

## 8. Data Model Relationships

How the core Pydantic models relate to each other and to Redis.

```mermaid
erDiagram
    PMAgentState {
        string session_id PK
        string pm_name
        string mode
        string current_node
        string release_id
        string release_label
        list aha_specs
        list portal_articles
        string plan_feedback
        list plan_feedback_history
        list mode_order
        list tool_calls
        list node_transitions
        string start_time
    }

    SessionRecord {
        string session_id PK
        string pm_name
        string pm_email
        string mode
        string release_label
        string start_time
        string end_time
        string status
        list tool_calls
        list node_transitions
    }

    ToolCallRecord {
        string tool_name
        dict params
        string timestamp
        string result
    }

    NodeTransition {
        string node
        string timestamp
    }

    PMContext {
        string pm_id
        string name
        list owned_products
        dict portal_folders
        string release_cadence_rules
        list upcoming_releases
    }

    AhaMapping {
        string product
        string aha_product_key
        string release_field_type
        string aia_version_prefix
        string shipped_tag
    }

    DocumentPlan {
        string rationale
    }

    ArticlePlan {
        string title
        string article_id
        string folder_id
        string planned_changes
        string refined_content
        string jira_url
        bool confirmed
    }

    IteratorState {
        int current_index
    }

    PMAgentState ||--|| PMContext : "pm_context"
    PMAgentState ||--o| DocumentPlan : "plan"
    PMAgentState ||--|| IteratorState : "update_iterator"
    PMAgentState ||--|| IteratorState : "create_iterator"
    PMContext ||--|{ AhaMapping : "aha_mappings (dict)"
    DocumentPlan ||--|{ ArticlePlan : "articles_to_update"
    DocumentPlan ||--|{ ArticlePlan : "articles_to_create"
    IteratorState ||--|{ ArticlePlan : "articles"
    IteratorState ||--|{ ArticlePlan : "confirmed_articles"
    PMAgentState ||--|{ ToolCallRecord : "tool_calls"
    PMAgentState ||--|{ NodeTransition : "node_transitions"
    SessionRecord ||--|{ ToolCallRecord : "tool_calls"
    SessionRecord ||--|{ NodeTransition : "node_transitions"
```

---

## 9. AIA vs Standard Release — Decision Flow

How the agent determines which Aha fetch strategy to use for each PM.

```mermaid
flowchart TD
    Start(["PM starts session\nwith pm_email"])

    LoadCtx["load_company_context(pm_email)\n→ PMContext.aha_mappings"]
    Start --> LoadCtx

    CheckProduct{"For PM's product:\naha_mappings.release_field_type"}

    LoadCtx --> CheckProduct

    AIA["'aia_version_tag'\nproduct_key = 'AIA'"]
    Standard["'standard_release'\nproduct_key = ECAI | ECKN | ECAD"]

    CheckProduct -->|"AIA product"| AIA
    CheckProduct -->|"ECAI / ECKN / ECAD"| Standard

    ListAIA["ReleaseConfirmNode:\nList AIA x.x.x version tags\nfrom Aha feature tags"]
    ListStd["ReleaseConfirmNode:\naha_list_releases(product_key)\nfilter: in_progress + planned\n(summary only — for PM selection)"]

    AIA --> ListAIA
    Standard --> ListStd

    PMPicksAIA["PM picks: 'AIA 1.2.0'"]
    PMPicksStd["PM picks: '25.03'"]

    ListAIA --> PMPicksAIA
    ListStd --> PMPicksStd

    FetchAIA["aha_get_release_features(\n  product_key='AIA',\n  tag='AIA 1.2.0',\n  fields=all\n)\n★ Single call — full details inline"]
    FetchStd["aha_get_release_features(\n  release_id='REL-001',\n  fields=all\n)\n★ Single call — full details inline"]

    PMPicksAIA --> FetchAIA
    PMPicksStd --> FetchStd

    FilterBoth["Filter both:\ncustom_fields[documents_impacted]\ncontains 'release notes'"]

    FetchAIA --> FilterBoth
    FetchStd --> FilterBoth

    CrossCheck{"Is product ECKN?"}
    FilterBoth --> CrossCheck

    FlagECAI["Flag ECAI-tagged features:\n'Requires ECAI review —\nloop in Prasanth / Carlos'"]
    Continue["Continue to plan generation\n(all feature details already inline)"]

    CrossCheck -->|"yes — check ECAI components"| FlagECAI
    CrossCheck -->|"no"| Continue
    FlagECAI --> Continue

    style AIA fill:#FDF2F8,stroke:#DB2777
    style Standard fill:#EFF6FF,stroke:#2563EB
    style FlagECAI fill:#FEF3C7,stroke:#D97706
```

---

## 10. Deployment Pipeline

CI/CD flow from branch to production.

```mermaid
flowchart TD
    Dev["feature/* branch\n(developer local)"] -->|"git push"| PrePush

    PrePush{"pre-push hook\nruff lint\npytest unit/"}
    PrePush -->|"pass"| PR
    PrePush -->|"fail"| Dev

    PR["PR opened\nfeature/* → dev"]

    PR --> CIDEV

    subgraph CIDEV["GitHub Actions — ci-dev.yml"]
        Lint["ruff check + format"]
        Types["mypy type check"]
        UnitTests["pytest unit/ + functional/\n--cov-fail-under=80"]
        DockerBuild["docker build verify"]

        Lint --> Types --> UnitTests --> DockerBuild
    end

    CIDEV -->|"all pass"| PRApproval["1 reviewer approval"]
    PRApproval --> MergeDev["merge to dev"]

    MergeDev --> DeployDev

    subgraph DeployDev["Deploy to Dev"]
        BuildECR["docker build + push ECR"]
        ECSdev["aws ecs update-service\npmm-orchestration\n--force-new-deployment"]
        WaitDev["aws ecs wait services-stable"]
        SmokeDev["pytest tests/smoke/\n--base-url=dev-alb"]
        FEDev["aws s3 sync frontend/\ncloudfront invalidation"]

        BuildECR --> ECSdev --> WaitDev --> SmokeDev --> FEDev
    end

    SmokeDev -->|"fail → auto-rollback"| RollbackDev["rollback-ecs.sh dev"]
    FEDev --> PRProd

    PRProd["PR opened\ndev → main"]

    PRProd --> CIProd

    subgraph CIProd["GitHub Actions — deploy-prod.yml"]
        FullSuite["pytest unit/ + functional/"]
        IntTest["pytest integration/\n--run-live --env=dev"]

        FullSuite --> IntTest
    end

    IntTest --> TLApproval

    TLApproval{"Manual approval\nGitHub Environments\nTech Lead clicks Approve"}

    TLApproval -->|"approved"| DeployProd

    subgraph DeployProd["Deploy to Production"]
        BuildProd["docker build + push ECR"]
        ECSProd["aws ecs update-service\npmm-orchestration"]
        WaitProd["aws ecs wait services-stable"]
        SmokeProd["pytest tests/smoke/\n--base-url=prod-alb"]
        FEProd["aws s3 sync frontend/\ncloudfront invalidation"]
        TagRelease["git tag v{version}-prod"]

        BuildProd --> ECSProd --> WaitProd --> SmokeProd --> FEProd --> TagRelease
    end

    SmokeProd -->|"fail → auto-rollback"| RollbackProd["rollback-ecs.sh prod"]

    style CIDEV fill:#EFF6FF,stroke:#2563EB
    style DeployDev fill:#F0FDF4,stroke:#16A34A
    style CIProd fill:#EFF6FF,stroke:#2563EB
    style DeployProd fill:#FDF2F8,stroke:#DB2777
    style TLApproval fill:#FEF3C7,stroke:#D97706
    style PrePush fill:#FEF3C7,stroke:#D97706
```

---

---

## 11. Skill Script Execution Model — All Scripts Run as Lambdas

This diagram answers: **"The skill has scripts — how do they execute?"**

Short answer: **All skill scripts are deployed as Lambda functions.** The orchestration service invokes them via `boto3 lambda.invoke`. Each invocation is stateless — no connection pools, no rate limiters, no in-process token caching.

```mermaid
flowchart TD
    Question(["Skill has a script.
How does it execute?"])

    SkillScript{"Is it a skill API client
(Aha, eGain, Jira, etc.)?"}

    EventDriven{"Is it triggered by
an external event?"}

    SkillLambda["✅ Handled by pmm-skill-client

Generic Lambda — reads API_CONFIG from payload:

auth.type=basic (e.g. Aha, Jira):
  Fetches credentials from Secrets Manager
  Builds Basic auth header
  Fresh httpx client per invocation
  No rate limiter — 429 = error to agent

auth.type=basic_onbehalf (e.g. eGain):
  Fetches credentials from Secrets Manager
  Builds on-behalf-of-customer auth header
  Fresh httpx client per invocation

Adding a new skill = new tools.py only
  No Lambda code changes needed"]

    EventLambda["✅ Deploy as event Lambda

Example in this project:
context-refresher —
triggered by S3 ObjectCreated,
runs once, exits"]

    Question --> SkillScript
    SkillScript -->|"Yes — makes API calls
on behalf of agent"| SkillLambda
    SkillScript -->|"No"| EventDriven
    EventDriven -->|"Yes — S3 event,
webhook, schedule"| EventLambda

    style SkillLambda fill:#F0FDF4,stroke:#16A34A
    style EventLambda fill:#EFF6FF,stroke:#2563EB
```

### Why all skill scripts run as Lambdas

| Property | Lambda approach | Trade-off |
|---|---|---|
| **Single generic Lambda** | One `pmm-skill-client` handles all skills — auth is config-driven from `tools.py` | Adding a new skill requires zero Lambda code changes |
| **No connection pool management** | Each invocation creates a fresh httpx client and discards it | Slightly higher latency per call (~50-200ms overhead) |
| **No process singletons** | No client objects in the ECS process | Simpler ECS service — fewer failure modes |
| **No shared rate limiter** | If Aha returns 429, the Lambda propagates the error | Concurrent PMs could hit the 100 req/min limit; agent surfaces the error to the PM |
| **Config-driven auth** | `API_CONFIG` from `tools.py` tells the Lambda how to authenticate (basic, basic_onbehalf) | New auth types require Lambda code changes, but new skills with existing auth types do not |
| **Credentials isolated** | Lambda fetches credentials from Secrets Manager using `credentials_secret` from payload | Orchestration service never touches API keys — better security boundary |

### Current Lambda inventory

| Lambda | Trigger | Purpose |
|---|---|---|
| `pmm-skill-client` | `boto3 lambda.invoke` from orchestration service | Generic skill executor — reads `API_CONFIG` from payload, authenticates per `auth.type`, makes API call, returns result |
| `pmm-context-refresher` | S3 `ObjectCreated` on `context/` | Calls `POST /internal/context/invalidate` on orchestration service |

---

## Diagram Index

| # | Diagram | What it shows |
|---|---|---|
| 1 | System Overview | All components and who calls what |
| 2 | Graph Node Flow | Complete PydanticAI Graph with all 21 BaseNode classes, 6 HITL gates, and Graph.iter() for HITL pause/resume |
| 3 | Skill Folder Architecture | How SKILL.md + tools.py + scripts/ wire together |
| 4 | Concurrent Session Model | Lambda-based stateless clients, per-session isolation via Redis |
| 5 | Auth and Credential Flow | Sequence: tool call → Lambda → Secrets Manager → API (LLM and ECS never see creds) |
| 6 | HITL Session Lifecycle | Full multi-turn conversation across 3 HTTP requests |
| 7 | AWS Infrastructure | Network topology, security groups, resource placement |
| 8 | Data Model Relationships | ER diagram: PMAgentState, PMContext, DocumentPlan, IteratorState |
| 9 | AIA vs Standard Release | Decision tree for AIA version-tag vs standard release fetch strategy |
| 10 | Deployment Pipeline | CI/CD from branch → dev → prod with approval gates |
| 11 | Script Execution Model | Single generic Lambda (`pmm-skill-client`), config-driven auth from tools.py |
