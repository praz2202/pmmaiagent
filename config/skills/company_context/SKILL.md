---
name: company-context
description: >
  Format specification for company-context.md (S3). Not injected into agent prompts.
  Reference for developers and the parser. Defines expected Markdown structure.
---

# Company Context — Format Specification

## About the company

eGain Corporation is a SaaS platform for customer engagement and knowledge management.
Products include AI Agent (AIA), AI Services (ECAI — Search + Instant Answers),
Knowledge (ECKN — authoring, publishing, portal), and Advisor Desktop (ECAD — agent desktop).
Product documentation lives in the eGain Knowledge portal (api.egain.cloud).

## How this file is used

`context/company-context.md` lives in S3. It contains business data that changes
without code deploys — PM assignments, portal IDs, release schedules.

At session start, `s3_loader.py` parses it into a typed `PMContext` struct.
This spec documents the expected format so the parser and data stay in sync.

---

## Required sections and table formats

### 1. PM to Product Ownership

Section header: `## PM to Product Ownership`

| Column | Required | Description |
|---|---|---|
| PM Name | Yes | Display name — must match frontend dropdown exactly |
| Email | Yes | Lookup key for pm_context |
| Owned Products | Yes | Comma-separated product codes: `AIA, ECAI` |
| Role | No | e.g. `PM — AI Agent`, `PM Manager` |
| Reports To | No | Manager name — for escalation routing |

### 2. Aha Product Mappings

Section header: `## Aha Product Mappings`

| Column | Required | Description |
|---|---|---|
| Product Name | Yes | Human-readable: `AI Agent`, `AI Services`, etc. |
| Aha Code | Yes | `AIA`, `ECAI`, `ECKN`, `ECAD` |
| Description | No | What the product does |
| Aha URL | No | Link to Aha product page |
| Release Tracking | Yes | `Version tags (AIA x.x.x)` or `Release attribute` |
| Notes | No | Release string format, cross-product notes |

Parser: if Release Tracking contains "version tag" or "AIA" → `release_field_type = "aia_version_tag"`, otherwise `"standard_release"`.

### 3. Release Tracking Rules

Section header: `## Release Tracking Rules`

Free-form text. Parsed as a single string (max 800 chars) into `pm_context.release_cadence_rules`.

### 4. Documents Impacted Attribute

Section header: `## Documents Impacted Attribute`

Table of tag values and meanings. Injected as text into agent prompts for
feature filtering decisions. Not parsed into a struct.

### 5. Upcoming Releases

Section header: `## Upcoming Releases`

| Column | Required | Description |
|---|---|---|
| Release / Version | Yes | `AIA 1.2.0` or `ECAI-R-53 21.23.1.0` |
| Product(s) | Yes | Comma-separated codes |
| Target Date | Yes | `March 2025` |
| Status | No | `In Progress`, `Planning` |

Filtered to PM's owned products at parse time.

### 6. eGain Portal Context

Section header: `## eGain Portal Context`

ONE shared portal for all products. Structure:
- Portal Short ID (e.g. `2ibo79`)
- Article ID pattern (e.g. `EASY-{number}`)
- Topic hierarchy as a tree diagram with topic IDs
- Topic ID table: `| Topic | Topic ID | Product | Notes |`
- Portal navigation rules (routing features to the right topics)
- Release notes article format (Jira Link, Overview, Release Notes, Helpdoc needed, etc.)

```
## eGain Portal Context

- Portal Short ID: `2ibo79`
- Article ID pattern: `EASY-{number}`

### Portal Topic Hierarchy

Home
├── AI Agent for Contact Center (308200000003062)
│   ├── Connectors (308200000003123)
│   │   ├── Channels (308200000003124)
│   │   └── Customisations (308200000003126)
│   ├── New Features for AI Agent 1.1.0
│   └── Upcoming Features for AI Agent 1.2.0
├── AI Agent for Customers (308200000003063)
├── AI Agent for Enterprise (308200000003064)
├── Search 2.0 (308200000003066)
└── Instant Answers (308200000003065)

### Topic IDs
| Topic | Topic ID | Product | Notes |
```

Parser extracts: `PortalContext(portal_short_id, topics: [PortalTopic(name, topic_id, product, notes)])`

---

## Parsed output: pm_context

```
pm_context.name                    → "Prasanth Sai"
pm_context.email                   → "prasanth.sai@egain.com"
pm_context.owned_products          → ["AIA", "ECAI"]
pm_context.reports_to              → "Varsha Thalange"
pm_context.aha_mappings            → {"AIA": AhaMapping(...), "ECAI": AhaMapping(...)}
pm_context.portal_context          → PortalContext(portal_short_id="2ibo79", topics=[...])
pm_context.release_cadence_rules   → text (max 800 chars)
pm_context.documents_impacted_rules → text (Documents Impacted tag meanings)
pm_context.upcoming_releases     → [{release, products, target}] filtered to PM
```
