---
type: decision
id: 20261120-0915-commit-message-multiline-field
date: 2026-11-20
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/sync_prompt_dialog.py
tags: [sync, ui]
participants: [engineer, design agent]
---

# Multi-line Commit Message Field Below The File Tree

## Context
`SyncDialog` stacks a summary label, the file tree and the button row. The commit message
needs a field in that dialog.

## Options Considered

### Option 1: Single-line `QLineEdit`
- ✅ Compact, and Enter confirms the dialog
- ❌ No room for a longer explanation

### Option 2: Multi-line `QPlainTextEdit`
- ✅ Room for a longer explanation of the change
- ❌ Takes vertical space from the tree
- ❌ Enter inserts a newline instead of confirming

## Decision
We chose **a multi-line `QPlainTextEdit`**. It is about 3 lines high, does not stretch,
and has a "Commit message" label and placeholder text. It sits between the tree and the
button row, so the user picks files first and then describes the change. The tree keeps
its stretch factor.

## Consequences
### Positive
- ✅ Users can explain larger changes
### Negative
- ⚠️ Newlines in messages may look awkward in the version history table. Fixing that is a
  follow-up task.
### Neutral
- The message is passed on as typed, apart from stripping surrounding whitespace

## Related Decisions
- [20261119-1600-commit-message-data-syncs-only](20261119-1600-commit-message-data-syncs-only.md)
- [20261120-0900-commit-message-optional](20261120-0900-commit-message-optional.md)
