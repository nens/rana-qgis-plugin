---
type: decision
id: 20261120-0930-commit-message-explicit-parameter
date: 2026-11-20
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/sync_prompt_dialog.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
  - rana_qgis_plugin/layer_management/close_sync_prompt.py
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/workers/upload.py
tags: [sync, upload]
participants: [engineer, design agent]
---

# The Commit Message Is Passed As An Explicit Parameter

## Context
The message is entered in `SyncDialog` and must end up in the finish-upload payload built by
`prepare_existing_file_upload`. The path in between is
`dispatch_selected` → `dispatch_data_items` → `Loader.upload_existing_files` →
`prepare_existing_file_upload`. `prepare_existing_file_upload` runs twice: once normally, and
again with `overwrite=True` after a conflict prompt. One message applies to the whole batch.

## Options Considered

### Option 1: Explicit parameter
Add `message: str | None = None` to `dispatch_data_items`, `upload_existing_files` and
`prepare_existing_file_upload`. Callers bind the message when they pass the callback, e.g.
`lambda items: self.dispatch_data_items(items, dialog.message())`.
- ✅ Explicit, with one value per batch, which matches "one message for all"
- ✅ `dispatch_selected` stays unchanged
- ❌ Three signatures change

### Option 2: Field on each `UploadableLayerItem`
- ✅ Fewer signature changes
- ❌ Changes items that were captured before the dialog opened
- ❌ A per-item field suggests per-file messages, which we don't support

## Decision
We chose **an explicit parameter**. `SyncDialog.message()` returns the stripped text, or
`None` when it is empty. `prepare_existing_file_upload` sets `payload["message"]` only when
the message is not `None`. Both prepare calls in `upload_existing_files`, the normal one and
the overwrite one, receive the message.

## Consequences
### Positive
- ✅ Data flow is easy to trace and to test
### Negative
- ⚠️ Callers must remember to bind the message when they pass the data callback
### Neutral
- The defaults keep other callers working unchanged
- Commit messages for new-file uploads can be added later the same way: an optional
  `message` parameter on `prepare_new_file_upload`. `UploadJob` and `FileUploadTask` need
  no changes, because the message travels in the payload.

## Related Decisions
- [20261111-1200-sync-selection-flow](20261111-1200-sync-selection-flow.md)
- [20261120-0900-commit-message-optional](20261120-0900-commit-message-optional.md)
