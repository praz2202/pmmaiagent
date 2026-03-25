---
name: release_features
description: >
  Fetching and reviewing release features from Aha. Use when a PM asks about
  features in a release, wants to see what's in a release, or needs feature
  details for documentation. Trigger on: release features, feature list,
  what's in this release, feature details.
---

# Release Features Skill

## Two-level fetch

**Level 1 — Feature list (lightweight):** Fetch feature titles + Jira URLs +
Documents Impacted tags. Present to PM for review. PM can ignore features.

**Level 2 — Full content (on demand):** Only after PM confirms which features
to work with. Fetch full description + attachments + requirements for specific features.
Requirements are sub-tasks under a feature — include them when writing release notes
or understanding the full scope of a feature.

## How release tracking works

Release tracking differs by product — use `get_release_tracking()` context
tool to load the rules for the PM's product before fetching.

- **AIA:** uses version TAGS (e.g. `AIA 1.2.0`), NOT the Release field
- **ECAI, ECKN, ECAD:** use Release ATTRIBUTE with format `{CODE}-R-{num} {version}`
  The actual version is AFTER the space (e.g. `ECAI-R-53 21.23.1.0` → version `21.23.1.0`)

## Documents Impacted handling

After fetching features, check the Documents Impacted tags on each feature.
Use `get_document_rules()` context tool to load the tag meanings.
Flag contradictions (e.g. "No documentation impact" + "Release Notes") to PM.
If a feature has empty Documents Impacted → ask PM to update it in Aha.

## Gotchas

- Don't fetch full feature content (Level 2) until PM confirms the feature list
- AIA does NOT use the Release field — use tags instead
- For standard products, parse version from release string: ignore the prefix before the space
- PMs may say "21.23.1" or "21.23.1.0" — both refer to the same release. Match flexibly:
  "21.23.1" should match "ECAI-R-53 21.23.1.0". Always try appending ".0" if no exact match.
- Rate limit is 100 req/min shared across all sessions — 429 errors propagate to PM
- Jira link is in `integration_fields` (look for service_name="jira", name="key"). Full URL: `https://beetle.egain.com/browse/{key}`. NEVER fabricate or guess Jira links.
