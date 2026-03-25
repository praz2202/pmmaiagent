---
name: portal_articles
description: >
  Browsing, comparing, and suggesting updates/creates for eGain portal articles.
  Use when a PM asks to update the portal, check what's in the portal, create
  a new article, or put release notes into the portal. Trigger on: update portal,
  portal articles, create article, check portal, put this in the portal.
---

# Portal Articles Skill

## "Update the portal" workflow

When PM asks to update the portal for a release (e.g. "update portal for AIA 1.2.0"):

**Step 1 — Gather data:**
- Fetch features for the release (Level 1 — titles + Documents Impacted tags + Jira links)
- Get document rules to understand tag meanings
- Show feature list to PM with ALL their tags. A feature can have MULTIPLE tags.
  For example, a feature tagged "Release Notes" AND "User Guides" needs BOTH:
  - A release notes article under the release topic
  - A user guide article update in the relevant product topic
- Do NOT separate features into either/or categories. Show each feature with ALL its tags.
- PM can ignore features

**Step 2 — Scan the portal comprehensively:**
For features tagged "Release Notes":
- **AIA release notes:** ALL AI Agent release notes go under **"AI Agent for Contact Center"** topic —
  regardless of whether the feature is for AIACC, AI Agent for Enterprise, or AI Agent for Customers.
  Sub-topic format: "New Features for AI Agent {version}" or "Upcoming Features for AI Agent {version}"

- **ECAI release notes:** Search features go under **"Search 2.0"** topic. IA features go under
  **"Instant Answers"** topic. They are SEPARATE — never combine them.
  Sub-topic format under Search 2.0: "New Features for Search {version}"
  Sub-topic format under Instant Answers: "New Features for Instant Answers {version}"
  Decide per feature: is it a Search feature or an IA feature? Route accordingly.
- Check if a release sub-topic exists under "AI Agent for Contact Center"
  (e.g. "Upcoming Features for AI Agent 1.2.0" or "New Features for AI Agent 1.2.0")
- If found:
  - **Browse the articles inside that release topic** using `browse_portal_topic`
  - Compare existing article titles with features
  - If an article for that feature already exists → suggest **UPDATE** (fetch content to see what to change)
  - If no matching article exists → suggest **CREATE** new article in that topic
- If release topic not found → suggest creating a new sub-topic under "AI Agent for Contact Center"
  named "Upcoming Features for AI Agent {version}"

For features tagged "User Guides" or "Online Help":
- For EACH feature, decide which specific topic it belongs to based on the feature description:
  - Is it about connectors/channels? → browse Connectors or Channels topic
  - Is it about general AI Agent CC functionality? → browse AI Agent for Contact Center topic
  - Is it about customer-facing AI Agent? → browse AI Agent for Customers topic
  - Is it about Search? → browse Search 2.0 topic
  - Is it about Instant Answers? → browse Instant Answers topic
- Only fetch article titles from the RELEVANT topic (not all topics — saves API calls)
- Match feature to article titles. If a title matches:
  - Fetch the full article content with `read_portal_article` to see what's there
  - Suggest the exact update based on the feature vs existing content comparison
- If no title matches → suggest creating a new article in that topic
- If no existing topic fits the feature → suggest creating a new topic AND article

**Step 3 — Present a full recommendation list:**
Show PM a single comprehensive list with ALL recommendations:

**Updates needed:**
- Article X in topic Y — update because of feature Z (brief reason)
- Article A in topic B — update because of feature C

**New articles needed:**
- Create article in topic X — for feature Y (no existing article covers this)

**Topic changes:**
- Rename "Upcoming Features for AI Agent 1.2.0" → "New Features for AI Agent 1.2.0" (if release shipped)

**Step 4 — PM reviews the full list:**
PM can say: "ignore article X", "yes to all", "skip the connectors updates", etc.

**Step 5 — Execute one by one:**
After PM approves, present each recommendation ONE at a time:
- For updates: show the article name, which topic it's in, and the exact updated content in Markdown
- For creates: show the topic > sub-topic, suggested article title, and full content in Markdown
- PM reviews each one → approve, edit, or skip → move to next

## Presenting topics

When showing portal topics to the PM, always include:
- **articleCountInTopic** — articles directly in that topic (not in sub-topics)
- **articleCountInTopicTree** — total articles including all sub-topics

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

## Gotchas

- The API is READ-ONLY — no create, update, or delete endpoints
- company-context.md only has TOP-LEVEL topic IDs — use `get_child_topics()` for sub-topics
- Long IDs auto-convert to short IDs (EASY-{last 4 digits}) — you can pass either format
- Use article title + summary (Level 1) before fetching full content (Level 2)
- Content output is Markdown for PM review — PM applies in portal manually
- Max topic depth is 2 levels (topic → sub-topic → sub-sub-topic)
