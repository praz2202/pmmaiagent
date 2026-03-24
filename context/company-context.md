# eGain PMM Agent — Company Context

eGain Corporation is a SaaS platform for customer engagement and knowledge management.
This file contains business data used by the PMM AI Agent. Updated in S3 without code deploys.

---

## PM to Product Ownership

| PM Name | Email | Owned Products | Role | Reports To |
|---|---|---|---|---|
| Varsha Thalange | varsha.thalange@egain.com | AIA, ECAI, ECKN, ECAD | PM Manager | Ashu Roy (CEO) |
| Prasanth Sai | prasanth.sai@egain.com | AIA, ECAI | PM — AI Agent + AI Services | Varsha Thalange |
| Aiushe Mishra | aiushe.mishra@egain.com | AIA | PM — AI Agent | Prasanth Sai |
| Carlos España | carlos.espana@egain.com | ECAI | PM — AI Services | Prasanth Sai |
| Ankur Mehta | ankur.mehta@egain.com | ECKN | PM — Knowledge | Varsha Thalange |
| Peter Huang | peter.huang@egain.com | ECKN | PM — Knowledge | Ankur Mehta |
| Kevin Dohina | kevin.dohina@egain.com | ECAD | PM — Advisor Desktop | Varsha Thalange |

> Note: ECKN features may have ECAI dependencies. Flag these for Prasanth Sai / Carlos España review.

---

## Aha Product Mappings

| Product Name | Aha Code | Description | Aha URL | Release Tracking | Notes |
|---|---|---|---|---|---|
| AI Agent | AIA | Conversational AI agent platform — virtual assistants, agent handoff, conversation flows | egain.aha.io/products/AIA | Version tags (`AIA 1.2.0`) | Does NOT use Release attribute |
| AI Services | ECAI | AI backend services — Search and Instant Answers (IA) | egain.aha.io/products/ECAI | Release attribute | Format: `ECAI-R-{num} {version}` |
| Knowledge | ECKN | Knowledge management platform — authoring, publishing, portal | egain.aha.io/products/ECKN | Release attribute | Format: `ECKN-R-{num} {version}` |
| Advisor Desktop | ECAD | Agent desktop application — case management, customer interaction | egain.aha.io/products/ECAD | Release attribute | Format: `ECAD-R-{num} {version}` |

---

## Release Tracking Rules

### AIA (AI Agent)
- Does NOT use the Aha Release attribute
- Releases are tracked via version TAGS on features: `AIA 1.0.0`, `AIA 1.2.0`, `AIA 2.0.0`
- To fetch features for a release: search by tag (e.g. `tag=AIA 1.2.0`)
- All AIA features: egain.aha.io/products/AIA/feature_cards

### Standard Products (ECAI, ECKN, ECAD)
- Use the Release ATTRIBUTE on each feature
- Release string format: `{CODE}-R-{num} {version}`
  - Example: `ECAI-R-53 21.23.1.0` → actual version is `21.23.1.0`
  - Example: `ECKN-R-116 21.21.4.0` → actual version is `21.21.4.0`
- Ignore the prefix (e.g. `ECAI-R-53`) — only use the version number after the space

### Cross-product: ECKN + ECAI
- ECKN features may depend on ECAI components
- When found: flag and note Prasanth Sai / Carlos España should review

---

## Documents Impacted Attribute

Every feature in Aha has a `Documents Impacted` custom field. This determines
what documentation action is needed for that feature.

| Tag Value | Action |
|---|---|
| `Release Notes` | Feature must be included in release notes |
| `User Guides` or `Online Help` | Feature needs a portal article update/create in eGain |
| `No documentation impact` | Skip — no documentation needed for this feature |
| *(empty / not set)* | PM has not updated this in Aha — ask PM to set it before proceeding |

**Multiple tags:** A feature can have multiple tags. For example, both `Release Notes`
and `User Guides` means it needs BOTH release notes AND a portal update.

**Contradiction handling:** If a feature has `No documentation impact` AND another tag
like `Release Notes` or `User Guides`, this is a contradiction. Flag it to the PM.

---

## eGain Portal Context

There is ONE shared portal for all products. Currently it has content for
AI Agent (AIA) and AI Services (ECAI — Search + Instant Answers).

- Portal Short ID: `2ibo79`
- Article ID pattern: `EASY-{number}` (e.g. `EASY-17468`, `EASY-17368`)

### Portal Topic Hierarchy

```
Home
├── AI Agent for Contact Center (308200000003062)
│   Contains: articles about AI Agent for CC features and guides
│   ├── Connectors (308200000003123)
│   │   ├── Channels (308200000003124)
│   │   └── Customisations (308200000003126)
│   ├── New Features for AI Agent 1.1.0       ← released features
│   ├── Upcoming Features for AI Agent 1.2.0  ← unreleased features
│   └── (more release/upcoming sub-topics per version)
│
├── AI Agent for Customers (308200000003063)
│   Contains: articles about AI Agent for customer-facing use cases
│   └── (no Connectors/Channels sub-topics yet)
│
├── AI Agent for Enterprise (308200000003064)
│   Contains: articles about AI Agent for enterprise use cases
│   └── (no Connectors/Channels sub-topics yet)
│
├── Search 2.0 (308200000003066)
│   Contains: articles about Search features and configuration
│   ├── New Features for Search 21.22.2       ← released features
│   ├── Upcoming Features for Search ...      ← unreleased features
│   └── (more release/upcoming sub-topics per version)
│
└── Instant Answers (308200000003065)
    Contains: articles about Instant Answers features and configuration
    ├── New Features for Instant Answers 21.23.0  ← released features
    ├── Upcoming Features for Instant Answers ... ← unreleased features
    └── (more release/upcoming sub-topics per version)
```

### Topic IDs

These are LONG IDs. For eGain v4 API calls, convert to short form: `EASY-{last 4 digits}`.
Example: `308200000003062` → `EASY-3062`. Sub-topics are discovered via `getchildtopics` API.

| Topic | Topic ID (long) | Short ID | Product | Notes |
|---|---|---|---|---|
| AI Agent for Contact Center | 308200000003062 | EASY-3062 | AIA | Top-level. Sub-topics discovered via API. |
| Connectors | 308200000003123 | EASY-3123 | AIA | Sub-topic under AI Agent for CC |
| Channels | 308200000003124 | EASY-3124 | AIA | Sub-topic under Connectors |
| Customisations | 308200000003126 | EASY-3126 | AIA | Sub-topic under Connectors |
| AI Agent for Customers | 308200000003063 | EASY-3063 | AIA | Top-level. No sub-topics yet. |
| AI Agent for Enterprise | 308200000003064 | EASY-3064 | AIA | Top-level. No sub-topics yet. |
| Search 2.0 | 308200000003066 | EASY-3066 | ECAI | Top-level. Sub-topics discovered via API. |
| Instant Answers | 308200000003065 | EASY-3065 | ECAI | Top-level. Sub-topics discovered via API. |

### Portal Navigation Rules

**Routing AI Agent features:**
- First ask: is this feature for AI Agent for CC, Customers, or Enterprise?
- Feature guide articles → listed directly under the respective topic
- Release features → in sub-topics named `New Features for AI Agent {version}` or `Upcoming Features for AI Agent {version}`
- Connector-related features → under Connectors → Channels or Customisations
- If no fitting connector sub-topic exists → suggest PM create a new topic

**Routing AI Services features:**
- Search features → under Search 2.0 topic
- Instant Answers features → under Instant Answers topic
- Release features → in sub-topics named `New Features for Search {version}` or `New Features for Instant Answers {version}`

**Release sub-topic naming:**
- Released features: `New Features for {product} {version}`
- Unreleased features: `Upcoming Features for {product} {version}`
- After a release ships: suggest PM rename `Upcoming Features...` → `New Features...`
- Check if existing release sub-topics need updates based on Aha features

**Missing topics:**
- AI Agent for Customers and Enterprise do NOT have Connectors/Channels sub-topics
- If a connector feature is for Customers or Enterprise → inform PM to create the topic first

### Release Notes Article Format

Articles under `New Features for...` or `Upcoming Features for...` topics follow this
structured format. Each article is one feature:

| Field | Description |
|---|---|
| Jira Link | Link to the Jira ticket (e.g. `https://beetle.egain.com/browse/EGS-88109`) |
| Overview | Brief description of the feature |
| Release Notes | The release notes text for this feature |
| Helpdoc update needed? | `Yes` / blank — whether a help doc article needs updating |
| Which Helpdoc | Name of the help doc article to update |
| Knowledge Hub Article update needed? | `Yes` / blank — whether a KHub article needs updating |
| Which KHub Article | Name of the KHub article to update |

When creating or updating release notes articles, follow this format.
The `Helpdoc update needed?` and `Which Helpdoc` fields signal which OTHER
portal articles may also need updating for this feature.
