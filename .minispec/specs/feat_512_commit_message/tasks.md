---
feature: feat_512_commit_message
status: planned
created: 2026-11-20
chunk_size: adaptive
total_tasks: 4
estimated_lines: 180
---

# Commit Messages For Sync Tasks

## Overview
Add an optional, multi-line commit message to `SyncDialog` for data syncs. Pass it through
the data dispatch and the loader into the finish-upload payload as `message`. See
[design.md](design.md).

## Task List

### Core Implementation

#### Task 1: Message in the upload payload [P]
- **Estimate:** ~40 lines including tests
- **Parallel:** Can run with Task 2
- **Files:** `rana_qgis_plugin/workers/upload.py`, `rana_qgis_plugin/loader.py`,
  `tests/utils/test_upload.py`
- **Description:**
  - `prepare_existing_file_upload(..., message: str | None = None)` sets
    `payload["message"] = message` when `message` is not `None`.
  - `Loader.upload_existing_files(items, message: str | None = None)` passes `message` to
    both `prepare_existing_file_upload` calls: the first pass and the `overwrite=True`
    pass after a conflict.
- **Depends on:** None
- **Acceptance:** The payload has a `message` key only when a message is given. Existing
  behaviour is unchanged when no message is passed. Both prepare calls in
  `upload_existing_files` receive the message (checked by reading the code; there is no
  loader test for this, see Notes).
- **Evidence:** New tests in `tests/utils/test_upload.py` pass (payload with message, and
  without message). The existing unit tests pass.

#### Task 2: Commit message field in `SyncDialog` [P]
- **Estimate:** ~70 lines including tests
- **Parallel:** Can run with Task 1
- **Files:** `rana_qgis_plugin/layer_management/sync_prompt_dialog.py`,
  `tests/layer_management/test_sync_dialog.py`
- **Description:**
  - A "Commit message" label and a `QPlainTextEdit` about 3 lines high, with placeholder
    text, between the tree and the button row. The tree keeps stretch factor 1, and the
    field does not stretch.
  - Only created when `changes` has data files.
  - Disabled while no data file is checked. Update it from the same `itemChanged` path as
    `update_confirm_button`. Typed text is kept.
  - `message() -> str | None` returns the stripped text, or `None` when the text is empty
    or only whitespace, or when the dialog has no field.
- **Depends on:** None
- **Acceptance:** Style-only dialogs have no field. Data and mixed dialogs show the field.
  Unchecking every data file disables the field, and checking one enables it again with
  the text intact.
- **Evidence:** New tests in `test_sync_dialog.py` pass:
  - the field is present or absent depending on the changes
  - the field is enabled or disabled as checkboxes are toggled
  - `message()` strips the text and returns `None` for empty input

### Integration

#### Task 3: Connect the callers
- **Estimate:** ~40 lines including tests
- **Files:** `rana_qgis_plugin/layer_management/layer_tree_menu.py`,
  `rana_qgis_plugin/layer_management/close_sync_prompt.py`,
  `tests/layer_management/test_layer_tree_menu_sync.py`,
  `tests/layer_management/sync_prompt_helpers.py`,
  close and removal prompt tests as needed
- **Description:**
  - `LayerTreeMenuProvider.dispatch_data_items(items, message: str | None = None)` passes
    the message to `loader.upload_existing_files`.
  - `LayerTreeMenuProvider.sync` and `SyncPromptAction.prompt_and_dispatch` bind the
    message when they pass the data callback to `dispatch_selected`, e.g.
    `lambda items: self.dispatch_data_items(items, dialog.message())`.
    `dispatch_selected` is unchanged.
  - Add `message()` to both `FakeSyncDialog`s. Let `SyncRecorder` / the fake loader record
    the message.
- **Depends on:** Task 1, Task 2
- **Acceptance:** On-demand sync and the close/removal prompts pass the dialog's message
  to the loader. When the user chooses "Continue without syncing" or cancels, nothing is
  uploaded, as before.
- **Evidence:** New or extended tests show the message reaching the data dispatch on both
  routes. The existing sync tests pass.

#### Task 4: Extend the e2e sync lifecycle test
- **Estimate:** ~30 lines
- **Files:** `e2e/test_layer_sync.py`
- **Description:**
  - Give `trigger_sync_action` an optional `message`. When it is set, the modal handler
    types it into the dialog's commit message field (`qtbot.keyClicks`) before clicking
    "Continue sync".
  - In `test_sync_lifecycle`, use a unique message for the vector data sync. After the
    sync, fetch `get_tenant_project_file_history_page(project_id, {"path": file_id,
    "limit": 1})` and assert that the newest item's `message` matches.
- **Depends on:** Task 3
- **Acceptance:** The e2e test types a message like a user would and checks it on Rana.
- **Evidence:** The e2e job passes in CI on the PR. Per AGENTS.md, it is not run locally.

## Notes
- Vertical slices (constitution IV): Tasks 1 and 2 are covered by unit tests only. Task 1
  has no UI, and the Task 2 field is not used until Task 3. Manual UI testing starts
  after Task 3, which completes the slice.
- E2E permission (constitution III): the engineer asked for Task 4, extending the
  existing e2e sync lifecycle test, during task planning on 2026-11-20.
- The setup script was not used. It writes to a root-level `specs/`, which AGENTS.md
  forbids.
- Nothing covers the overwrite-after-conflict pass automatically. The e2e test does not
  trigger a conflict, and a loader unit test would mostly test mocks. Test it by hand:
  create a conflict, choose overwrite, and check the message in the file history.
- Open question from the design: what the server stores when `message` is left out. Check
  by hand during Task 1 or Task 4. It doesn't change the implementation.
- Deferred (see design "Follow-Up Tasks"):
  - commit messages for new-file uploads (`prepare_new_file_upload` and a UI prompt)
  - showing multi-line messages in the version history table

## Manual UI Testing
- Layer panel → "Sync data to Rana" with several files: type a message, sync, and check
  that the file history shows it for each file.
- Layer panel → "Sync style(s) to Rana": no message field.
- Close a project with both data and style changes: uncheck all data files and check that
  the field is disabled. Check one again and check that the text comes back.
- Sync with an empty message: the upload succeeds.
- Conflict, then overwrite: the message is in the history.

## Progress
- [ ] Task 1: Message in the upload payload
- [ ] Task 2: Commit message field in `SyncDialog`
- [ ] Task 3: Connect the callers
- [ ] Task 4: Extend the e2e sync lifecycle test
