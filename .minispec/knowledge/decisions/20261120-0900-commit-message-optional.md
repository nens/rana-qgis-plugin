---
type: decision
id: 20261120-0900-commit-message-optional
date: 2026-11-20
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/sync_prompt_dialog.py
  - rana_qgis_plugin/workers/upload.py
tags: [sync, ui, upload]
participants: [engineer, design agent]
---

# Commit Message Is Optional And Omitted When Empty

## Context
The sync dialog gets a commit message field for data syncs. The API's `message` on
`UploadComplete` is optional. The dialog is also shown when closing a layer or project,
where users usually want to get out quickly.

## Options Considered

### Option 1: Optional, omit when empty
- ✅ No friction, especially on close
- ✅ The server decides what an empty message means
- ❌ History entries can be blank

### Option 2: Optional, plugin default text (e.g. "Synced from QGIS")
- ✅ History is never blank
- ❌ The generated text adds little information

### Option 3: Required
- ✅ Every version has a meaningful history entry
- ❌ Friction, and the close prompt becomes annoying

## Decision
We chose **Optional, omit when empty**. A whitespace-only message counts as empty. A
placeholder text explains what the field is for.

## Consequences
### Positive
- ✅ The sync flow is unchanged for users who don't care about messages
### Negative
- ⚠️ History can still contain versions without a meaningful message
### Neutral
- The `message` key is only added to the finish payload when it is non-empty

## Related Decisions
- [20261119-1600-commit-message-data-syncs-only](20261119-1600-commit-message-data-syncs-only.md)
