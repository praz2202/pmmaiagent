---
name: portal_articles
description: >
  Browsing, comparing, and suggesting updates/creates for eGain portal articles.
  Use when a PM asks to update the portal, check what's in the portal, create
  a new article, or put release notes into the portal. Trigger on: update portal,
  portal articles, create article, check portal, put this in the portal.
---

# Portal Articles Skill

## Presenting topics

When showing portal topics to the PM, always include:
- **articleCountInTopic** — articles directly in that topic (not in sub-topics)
- **articleCountInTopicTree** — total articles including all sub-topics
- The parent topic itself has articles too — don't skip it. For example,
  "AI Agent for Contact Center" has 25 articles directly in it plus 42 more in sub-topics.

Example format:
```
AI Agent for Contact Center (25 articles, 67 total with sub-topics)
  ├── Connectors (0 articles, 8 in sub-topics)
  ├── New Features for AI Agent 1.1.0 (5 articles)
  └── Upcoming Features for AI Agent 1.2.0 (6 articles)
```

## Two types of portal updates

### Release notes articles
- Go under "New Features for..." or "Upcoming Features for..." sub-topics
- Decision based on **article titles only** from `browse_portal_topic` — no need to read content
- Action: create new release notes articles, or check if they already exist

### User Guide / Online Help articles
- Go under the main product topics (AI Agent for CC, Connectors, Channels, Search 2.0, etc.)
- Decision flow:
  1. For each feature, decide which **specific topic** it belongs to (don't browse all topics)
  2. Fetch article titles from ONLY that topic using `browse_portal_topic`
  3. If a title matches the feature → fetch full content with `read_portal_article`
  4. Compare feature details vs existing article content → suggest exact update
  5. If no title matches → suggest creating a new article in that topic
  6. If no existing topic fits the feature → suggest creating a new topic + article

## API data per level

**Level 1 — `browse_portal_topic`:** Returns article **titles** and IDs only. No summary
field available in the list API. Article summary will be null — proceed with title only.

**Level 2 — `read_portal_article`:** Returns full article HTML content. Only call for
articles where the title suggests it needs updating.

## Missing article summaries

If `article_summary` is empty for an article:
- Decide based on article title alone
- Recommend to PM: "Article '{title}' has no summary. Please update it in the portal."
- If title is ambiguous, fetch full content to decide

## Create vs update decision

- **Update**: existing article clearly matches the feature → show article + suggested changes
- **Create**: no existing article → suggest topic > sub-topic > article title + content
- **Ambiguous**: present both options, let PM choose

## Portal topic navigation

company-context.md only has TOP-LEVEL topic IDs (e.g. "AI Agent for Contact Center").
Sub-topics (like "Connectors", "New Features for AI Agent 1.2.0") must be discovered
using `get_child_topics()`.

**Workflow to navigate the portal:**
1. Use `get_portal_structure()` context tool → gets top-level topic IDs
2. Call `get_child_topics(parent_topic_id)` → discovers sub-topics underneath
3. If needed, call `get_child_topics()` again on a sub-topic → level 2 (max depth)
4. Call `browse_portal_topic(topic_id)` → gets articles at any level

**ID format:** company-context.md has long IDs (e.g. `308200000003062`).
The tools auto-convert to short IDs (`EASY-3062`) for the eGain API.

**Key patterns:**
- Release features go in sub-topics: "New Features for {product} {version}" or
  "Upcoming Features for {product} {version}"
- After release ships: suggest PM rename "Upcoming Features..." → "New Features..."
- If no matching sub-topic exists: suggest PM create a new topic

## Release notes in portal

When PM says "put these release notes in the portal":
1. Get top-level topic ID from `get_portal_structure()`
2. Call `get_child_topics()` to find release sub-topics
3. Look for "New Features for..." or "Upcoming Features for..." matching the release
4. If found → suggest adding articles under it
5. If not found → suggest PM create the topic, then add articles
6. Present one article at a time for PM review

## Gotchas

- The API is READ-ONLY — no create, update, or delete endpoints
- company-context.md only has TOP-LEVEL topic IDs — use `get_child_topics()` for sub-topics
- Long IDs auto-convert to short IDs (EASY-{last 4 digits}) — you can pass either format
- Use article title + summary (Level 1) before fetching full content (Level 2)
- Content output is Markdown for PM review — PM applies in portal manually
- AI Agent for Customers/Enterprise may not have all sub-topics yet — inform PM
- Max topic depth is 2 levels (topic → sub-topic → sub-sub-topic)
