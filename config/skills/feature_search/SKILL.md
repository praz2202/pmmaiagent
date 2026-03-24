---
name: feature-search
description: >
  Finding features by name or keyword in Aha. Use when a PM asks about a
  specific feature by vague name or description. Trigger on: find feature,
  search feature, which feature, where is the feature about X.
---

# Feature Search Skill

## Workflow

1. PM asks about a feature by vague name (e.g. "the sync now button feature")
2. Ask PM: "Do you remember which release this is from?"
3. **PM knows release** → search within that product with the keyword
4. **PM doesn't know** → search across the product, show top results
5. Present matching features with: title, feature ID, Aha link, Documents Impacted tags
6. PM confirms the right one → proceed with whatever they need

## Gotchas

- Always ask for the release first — it narrows results significantly
- Show top 7 results max — don't overwhelm the PM
- Include Aha links so PM can click through to the full feature in Aha
- If no matches found, ask PM to rephrase or check the product
