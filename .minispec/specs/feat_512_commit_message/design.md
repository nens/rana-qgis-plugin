---
feature: feat_512_commit_message
status: planned
created: 2026-11-20
decisions:
  - 20261119-1600-commit-message-data-syncs-only
  - 20261120-0900-commit-message-optional
  - 20261120-0915-commit-message-multiline-field
  - 20261120-0930-commit-message-explicit-parameter
---

# Commit Messages For Sync Design

## Overview
`SyncDialog` gets an optional, multi-line commit message field for data syncs. One message
applies to every data file in the batch. It is sent as `message` on the finish-upload
request (`PUT /tenants/{t}/projects/{p}/files/upload`, schema `UploadComplete`), and the
version history dialog already shows it. Both routes share the dialog: the on-demand
"Sync data to Rana" from the layer panel, and the close/removal prompts. So both get the
field.

## Decisions
- [Commit messages only apply to data syncs](../../knowledge/decisions/20261119-1600-commit-message-data-syncs-only.md)
- [The commit message is optional and omitted when empty](../../knowledge/decisions/20261120-0900-commit-message-optional.md)
- [Multi-line commit message field below the file tree](../../knowledge/decisions/20261120-0915-commit-message-multiline-field.md)
- [The commit message is passed as an explicit parameter](../../knowledge/decisions/20261120-0930-commit-message-explicit-parameter.md)

## User Stories
- As a user syncing data from the layer panel, I want to describe my change, so that the
  file history explains what changed.
- As a user closing a layer or project with unsynced data, I want to add the same message
  when I choose to sync.
- As a user syncing several files at once, I want to type one message that applies to all
  of them.
- As a user who doesn't care about messages, I want to sync without being forced to type
  one.

## Components

### Sync dialog (`layer_management/sync_prompt_dialog.py`)
- A "Commit message" label and a `QPlainTextEdit` about 3 lines high, with placeholder
  text. They sit between the tree and the button row. The tree keeps stretch factor 1, and
  the field does not stretch.
- Shown only when `changes` contains data files. Style-only dialogs have no field.
- Disabled while no data file is checked, updated from the existing `itemChanged` →
  `update_confirm_button` hook (or a sibling method called from the same place). Typed text
  is kept while the field is disabled.
- `message() -> str | None` returns the stripped text, or `None` when the text is empty or
  only whitespace, or when the dialog has no field.

### Callers (`layer_tree_menu.py`, `close_sync_prompt.py`)
- Bind the message when passing the data callback to `dispatch_selected`, e.g.
  `lambda items: self.dispatch_data_items(items, dialog.message())`.
- `dispatch_selected` is unchanged.
- `LayerTreeMenuProvider.dispatch_data_items(items, message: str | None = None)` passes
  the message to the loader.

### Loader (`loader.py`)
- `Loader.upload_existing_files(items, message: str | None = None)` passes `message` to
  both `prepare_existing_file_upload` calls: the first pass and the `overwrite=True` pass
  after a conflict.

### Upload preparation (`workers/upload.py`)
- `prepare_existing_file_upload(..., message: str | None = None)` sets
  `payload["message"] = message` when `message` is not `None`. The `descriptor` handling
  is unchanged.

## Data Model
No new types. One optional `str | None` that travels with the batch. In the API payload,
the `message` key is only present when the message is non-empty.

## API/Interface
- `SyncDialog.message() -> str | None`
- `LayerTreeMenuProvider.dispatch_data_items(items, message=None)`
- `Loader.upload_existing_files(items, message=None)`
- `prepare_existing_file_upload(project, file, local_file=None, overwrite=False, message=None)`

## Testing
- `tests/layer_management/test_sync_dialog.py`:
  - the field is present with data changes and absent for style-only changes
  - the field is disabled when all data files are unchecked and enabled again when one
    is checked
  - `message()` strips the text and returns `None` for empty or whitespace-only input
- `tests/layer_management/test_layer_tree_menu_sync.py` and the close-prompt tests:
  the message reaches the data dispatch. `FakeSyncDialog` needs a `message()`.
- `tests/utils/test_upload.py`: the payload contains `message` only when one is given.
- `tests/loader/test_upload.py`: the message reaches the overwrite pass after a conflict.

## Manual UI Testing
- Layer panel → "Sync data to Rana" on a group with several files: type a message, sync,
  and check that the file history shows it for each file.
- Layer panel → "Sync style(s) to Rana": no message field.
- Close a project with both data and style changes: uncheck all data files and check that
  the field is disabled. Check one again and check that the text comes back.
- Sync with an empty message: the upload succeeds.
- Trigger a conflict and choose overwrite: the message is still in the history.

## Out Of Scope
- "Save revision" (the schematisation API, a separate flow)
- New-file uploads through the folder action (`Loader.upload_files`). See
  "Extension: new-file uploads" below.
- Style syncs, which don't create file versions
- Showing multi-line messages properly in the version history table (follow-up task)

## Extension: New-File Uploads
The design keeps this open, so it can be added later without rework:
- `prepare_new_file_upload` (`workers/upload.py`) also stores the start response as
  `UploadJob.payload`, which `FileUploadTask` sends when it finishes. So it can take the
  same optional `message: str | None = None` parameter, and add `payload["message"]` the
  same way `prepare_existing_file_upload` does.
- `FileUploadTask` and `UploadJob` need no changes for this feature or for the extension.
  The message lives entirely in the payload.
- The UI is the only missing part. New uploads start from `QFileDialog.getOpenFileNames`
  in `Loader.upload_files`, not from `SyncDialog`. They will need their own place to enter
  a message, for example a small prompt after picking files, with the same field behaviour
  (optional, multi-line, stripped, `None` when empty).
- The one-line payload rule (`if message: payload["message"] = message`) will then exist
  twice. Following the constitution's abstraction threshold, it stays inline until a third
  use appears.

## Open Questions
- What does the server store when `message` is left out: an empty string or a default?
  Check during implementation. It affects only the history display, not this design.

## Follow-Up Tasks
- Show multi-line commit messages properly in the version history table
  (`widgets/version_history_dialog.py`).
- Commit messages for new-file uploads (see "Extension: new-file uploads").
