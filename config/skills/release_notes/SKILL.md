---
name: release-notes
description: >
  Creating release notes for features. Use when a PM asks to create release
  notes, write release notes, or document a release. This skill has no tools —
  the agent generates content using LLM reasoning based on feature data.
  Trigger on: create release notes, write release notes, document release.
---

# Release Notes Skill (Knowledge Only)

## Article format

Each release notes article covers ONE feature and follows this format:

| Field | Description |
|---|---|
| Jira Link | Link to the Jira ticket from the feature's custom fields |
| Overview | Brief description of the feature (2-3 sentences) |
| Release Notes | The release notes text — what changed, what's new, how to use it |
| Helpdoc update needed? | Yes / No — does a help doc article need updating for this feature? |
| Which Helpdoc | Name of the help doc article to update (if applicable) |
| Knowledge Hub Article update needed? | Yes / No |
| Which KHub Article | Name of the KHub article to update (if applicable) |

## Workflow

1. PM says "create release notes for [release]"
2. Agent fetches features (Level 1) using release-features tools
3. Agent shows feature list → PM filters (ignore some, keep others)
4. For each confirmed feature, agent fetches full detail (Level 2)
5. Agent generates release notes in the article format above
6. Present ONE feature's release notes at a time → PM reviews
7. PM can edit/correct → agent updates → PM approves → next feature
8. Repeat until all features have release notes

## Content guidelines

- **Overview**: concise, factual. What the feature does, not marketing language.
- **Release Notes**: written for administrators/end users, not developers.
  Describe what changed from the user's perspective.
- **Helpdoc update**: check if the feature changes existing documentation.
  If yes, name the specific article that needs updating.
- Content in **Markdown** for PM review. PM converts when applying to portal.

## Gotchas

- Generate release notes ONE feature at a time — don't batch
- If PM says "change the overview" → update and show again, don't skip ahead
- The Jira Link comes from the feature's custom fields (see release-features skill)
- If Jira URL is missing, note it but don't block — PM can add it later
