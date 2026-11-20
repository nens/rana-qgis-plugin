---
type: decision
id: 20261119-1600-commit-message-data-syncs-only
date: 2026-11-19
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/sync_prompt_dialog.py
  - rana_qgis_plugin/workers/upload.py
tags: [sync, ui, upload]
participants: [engineer, design agent]
---

# Commit Messages Only Apply To Data Syncs

## Context
Users want to add a commit message when they sync files to Rana. The Rana API takes an
optional `message` on the finish-upload request (`PUT /tenants/{t}/projects/{p}/files/upload`,
schema `UploadComplete`). It returns that message per version from
`GET .../files/history`, which the version history dialog already shows.

Style syncs do not create a file version. `upload_file_styling` and
`upload_publication_style` store styling on the descriptor or publication, so a style sync
has nowhere to keep a message.

## Options Considered

### Option 1: Data syncs only
Show the message field only when the dialog contains data changes.
- ✅ The UI asks for a message only where it is stored
- ❌ The dialog layout depends on what is being synced

### Option 2: Always show the field and ignore it for styles
- ✅ Same layout every time
- ❌ A message typed for a style-only sync is silently lost

### Option 3: Always show the field and disable it for styles
- ✅ Consistent layout
- ❌ More UI state and a hint text that adds noise

The engineer first chose a field that stays visible and enabled whatever the checkbox
state. That was revised after noticing a problem in mixed data and style dialogs: when every
data file is unchecked, the field stays active but its message goes nowhere. The field is
now disabled while no data file is checked (see Consequences).

## Decision
We chose **Data syncs only**. A field that silently drops input is misleading. Disabling
the field adds state without adding value.

## Consequences
### Positive
- ✅ The UI reflects what the API stores
### Negative
- ⚠️ A mixed sync (data and style) applies the message to the data files only
### Neutral
- Style uploads are unchanged
- The field is shown when `changes` has data files. It is disabled while no data file is
  checked, using the existing `itemChanged` → `update_confirm_button` hook. Typed text is
  kept, so it comes back when the user checks a data file again. This avoids an active
  field whose message goes nowhere, for example in a mixed close prompt where the user
  has unchecked every data file.

## Code References
- Finish payload: `rana_qgis_plugin/workers/upload.py:prepare_existing_file_upload()`
- Style upload: `rana_qgis_plugin/workers/styling.py:make_file_style_upload_item()`
- History display: `rana_qgis_plugin/widgets/version_history_dialog.py`

## Related Decisions
- [20261111-1200-sync-selection-flow](20261111-1200-sync-selection-flow.md)
