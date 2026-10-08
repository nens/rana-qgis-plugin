---
feature: feat_442_file_history
status: planned
created: 2026-09-30
chunk_size: adaptive
total_tasks: 14
estimated_lines: 780
---

# File History Tasks

## Overview

Implements the `feat_442_file_history` design: a native `Version history`
context-menu action showing read-only Rana history for files/folders/root, a
schematisation revision-history dialog with a per-revision context menu, and
the `Rana Model` Create/Delete actions on that revision dialog. The
`Simulation` action remains a placeholder (deferred to a later feature).

None of this feature exists in the codebase yet (a stale `.pyc` was the only
remnant of a previously deleted dialog module), so this task list covers the
full vertical slice, not just the model-action increment.

## Task List

### Foundation

#### Task 1: Fetch one generic file-history page with standard errors
- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/utils/api.py`
- **Description:** Replace the unused aggregate history helper with
  `get_tenant_project_file_history_page(project_id, params)`. The helper
  performs exactly one request through the standard `simple_fetch()`
  raise-on-error path and returns the raw page, including `items` and `next`.
- **Depends on:** None
- **Acceptance:** A page response is returned unchanged with its `items` and
  `next` fields; a simulated failure raises `RanaFetchError`;
  `NetworkUnavailableError` is not swallowed.
- **Evidence:** Docker/manual verification of the native history flow; no
  transport-mocking unit test is retained by engineer decision.

#### Task 2: `HistoryDialog` base class
- **Estimate:** ~100 lines
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py` (new)
- **Description:** Abstract `QDialog` base (no Rana/3Di knowledge) owning a
  `QTableView`/`QStandardItemModel`, a Refresh button, an inline error label,
  and an empty-state label. Implements the fetch/refresh lifecycle (fetch on
  open, fetch on Refresh, disable Refresh while running, route
  `NetworkUnavailableError`/`RanaFetchError` to `error_signals`) as a template
  calling subclass hooks for window title, column headers, and
  fetch-and-map-rows. Follows the `FileInfoDialog` pattern
  (`widgets/file_info_dialog.py:142`).
- **Depends on:** None
- **Acceptance:** Class cannot be meaningfully instantiated on its own
  (hooks raise `NotImplementedError`); lifecycle methods exist and are
  exercised by Task 3/5's dialogs.
- **Evidence:** Imports cleanly; covered indirectly by Task 3 and Task 5
  manual/automated checks.

### Generic History (P1)

#### Task 3: `RanaHistoryDialog` [P]
- **Estimate:** ~60 lines
- **Parallel:** Can run with Task 5 (both depend only on Task 2)
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:** Concrete sibling of `HistoryDialog` for generic Rana
  history. Calls `get_tenant_project_file_history(project_id, params)` with
  `path` set to the file/folder path (omitted for root), maps entries to
  `Timestamp | User | Message` rows. User display: given+family name, then
  email, then `Unknown`.
- **Depends on:** Task 2
- **Acceptance:** Opening the dialog for a file, folder, and the `Files` root
  each produce the correct `path` param and populate rows correctly.
- **Evidence:** Manual test per design's "Manual UI Test Paths"; unit test
  for the user-display fallback logic if extracted as a pure function.

#### Task 4: Wire generic history context-menu action
- **Estimate:** ~35 lines
- **Files:** `rana_qgis_plugin/data_items/file_actions.py`,
  `rana_qgis_plugin/data_items/file_item.py`,
  `rana_qgis_plugin/data_items/folder_item.py`
- **Description:** Add `FileAction.VERSION_HISTORY` to every result of
  `get_file_actions`. `RanaFileDataItem.actions` opens `RanaHistoryDialog` for
  non-schematisation files. `RanaFolderDataItem.actions` opens it with
  `folder_path`. `RanaFilesDataItem` (root) opens it with an empty path.
- **Depends on:** Task 2, Task 3
- **Acceptance:** `Version history` appears in the context menu for a file,
  folder, and the `Files` root, and opens `RanaHistoryDialog` with the
  correct path.
- **Evidence:** Manual context-menu test for all three item types.

### Schematisation Revisions (P1)

#### Task 5: `SchematisationRevisionHistoryDialog` skeleton [P]
- **Estimate:** ~70 lines
- **Parallel:** Can run with Task 3 (both depend only on Task 2)
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:** Concrete sibling of `HistoryDialog` for schematisation
  revisions. Resolves the schematisation via `get_threedi_schematisation()`,
  then fetches the complete revision list via
  `ThreediCalls.fetch_schematisation_revisions()` (all pages, synchronously —
  required for exact model-limit enablement in Task 6). Maps base columns
  `#`, `Timestamp`, `User`, `Message`. Shows an inline error when 3Di
  authentication is unavailable.
- **Depends on:** Task 2
- **Acceptance:** Dialog opens for a schematisation file and lists all
  committed revisions with correct base columns; missing 3Di auth shows an
  inline error instead of raising.
- **Evidence:** Manual test with and without 3Di authentication configured.

#### Task 6: Revision action columns (`Simulation` placeholder + `Rana Model` enablement)
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:** Add `Simulation` and `Rana Model` button columns per
  revision row, using legacy enablement rules
  (`legacy/widgets/revisions_view.py:187-229`):
  `Simulation`="New", enabled only if `revision.has_threedimodel`;
  `Rana Model`="Delete" if the revision has a model, else "Create", enabled
  while the count of model-bearing revisions is below
  `schematisation.threedimodel_limit`. `Simulation` click is a no-op
  placeholder in this feature (still deferred). `Rana Model` click handlers
  are stubbed here and wired to real callbacks in Task 11/12.
- **Depends on:** Task 5
- **Acceptance:** Button labels/enabled-state/tooltips match the legacy rules
  for revisions with a model, without a model under the limit, and without a
  model at the limit.
- **Evidence:** Manual test across the three enablement states (compare
  against legacy `RevisionsView` behavior for the same schematisation).

#### Task 7: Wire schematisation file items to the revision dialog
- **Estimate:** ~20 lines
- **Files:** `rana_qgis_plugin/data_items/file_item.py`
- **Description:** `RanaFileDataItem.actions` opens
  `SchematisationRevisionHistoryDialog` instead of `RanaHistoryDialog` when
  `file_data.get("data_type") == "threedi_schematisation"`.
- **Depends on:** Task 5, Task 6
- **Acceptance:** `Version history` on a schematisation file opens the
  revision dialog; on any other file it opens the generic dialog.
- **Evidence:** Manual context-menu test on a schematisation vs. a vector
  file.

### Revision Context Menu (P1)

#### Task 8: `Open` / `Open in web viewer` per revision row
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py`,
  `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/utils/data_models.py`
- **Description:** Add a row context menu with `Open` and
  `Open in web viewer`. Extend `OpenSchematisationRequest` (and
  `Loader.resolve_schematisation`/`open_items`) to accept an explicit
  revision id, defaulting to `latest_revision` when not supplied, so the
  default `Open in QGIS` action is unaffected. `Open in web viewer` builds the
  schematisation's existing management URL with the selected revision's ID
  substituted (as legacy `RevisionsView` does) and calls
  `QDesktopServices.openUrl()`.
- **Depends on:** Task 5
- **Acceptance:** `Open` on a non-latest revision downloads/opens that
  revision, not the latest; the default schematisation `Open in QGIS` action
  (outside history) still opens the latest revision; `Open in web viewer`
  opens a URL containing the selected revision's ID.
- **Evidence:** Manual test: open two different revisions and confirm the
  correct one loads each time; confirm default open behavior is unchanged.

### Rana Model Actions

#### Task 9: Expose the model-tracker job response + processes URL helper [P]
- **Estimate:** ~30 lines
- **Parallel:** Can run with Task 10
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/utils/generic.py`
- **Description:** Change `Loader.start_model_tracker_process()` to `return`
  the execution response dict from `start_tenant_process()` on success (`None`
  on the existing failure paths), without changing its existing
  `bar_info`/`bar_error` presentation. Add `get_rana_processes_url(project_slug,
  job_id=None) -> str` in `utils/generic.py`, mirroring `get_rana_file_url()`:
  `{base_url()}/{tenant}/projects/{slug}?tab=2` plus `&job={job_id}` when a
  job ID is given.
- **Depends on:** None
- **Acceptance:** `save_revision()`'s existing call site is unaffected since
  it already ignores the return value; the new helper produces the expected
  URL with and without a job ID.
- **Evidence:** Unit test for `get_rana_processes_url()` (with/without
  `job_id`); existing upload/save-revision manual flow still works
  unchanged.

#### Task 10: `Loader.delete_schematisation_revision_3di_model()` [P]
- **Estimate:** ~40 lines
- **Parallel:** Can run with Task 9
- **Files:** `rana_qgis_plugin/loader.py`
- **Description:** New method
  `delete_schematisation_revision_3di_model(self, schematisation_id: int, revision_id: int) -> str | None`.
  Uses `get_threedi_api()` (returns an error string if unauthenticated),
  `ThreediCalls.fetch_schematisation_revision_3di_models()` to resolve the
  revision's model, then `ThreediCalls.delete_3di_model()`. Catches
  `ApiException` via the existing `extract_error_message()` helper
  (`simulation/upload_wizard/model_deletion.py:184` pattern) and returns the
  message; returns `None` on success. Follows the `delete_file`/`delete_folder`
  return-value convention (`loader.py:336`, `:351`).
- **Depends on:** None
- **Acceptance:** Deleting a revision's model returns `None` and the model is
  gone from `fetch_schematisation_revision_3di_models()`; a simulated
  `ApiException` returns a readable error string instead of raising.
- **Evidence:** Unit test with a mocked `ThreediCalls`/`threedi_api` covering
  success and the `ApiException` path.

#### Task 11: Wire the `Create` button
- **Estimate:** ~45 lines
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:** `Create` click calls
  `Loader.start_model_tracker_process(project_id, schematisation_id, schematisation_name, revision_id)`.
  On a non-`None` result: disable that row's Create button for the current
  dialog session (tooltip: "Model creation requested — click Refresh to check
  status") and show a `QMessageBox.information` with an HTML link to
  `get_rana_processes_url(project_slug, job.get("id"))`. No confirmation
  dialog. No automatic table refetch — state only updates via the dialog's
  existing manual Refresh.
- **Depends on:** Task 6, Task 9
- **Acceptance:** Clicking Create on an eligible row disables that row's
  button immediately and shows a popup with a clickable process link; other
  rows are unaffected; a manual Refresh re-fetches and recalculates real
  state.
- **Evidence:** Manual test per design's "Manual UI Test Paths" — Create,
  verify popup link opens the expected URL, verify disabled state persists
  until Refresh.

#### Task 12: Wire the `Delete` button
- **Estimate:** ~35 lines
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:** `Delete` click shows a `QMessageBox.question` confirmation
  ("Delete Rana model for revision #{number}? This cannot be undone."),
  consistent with `data_items/file_item.py:176`. On confirmation, calls
  `Loader.delete_schematisation_revision_3di_model()`. On error, shows
  `communication.show_error(error, parent=dialog)` and leaves the row
  unchanged. On success, re-runs the dialog's complete revision fetch so
  every row's Create-button enablement is recalculated against the new model
  count.
- **Depends on:** Task 6, Task 10
- **Acceptance:** Cancelling the confirmation makes no API call; a
  successful delete removes that revision's model and re-enables Create on
  other rows if the limit is no longer reached; a failed delete shows an
  error and leaves table state untouched.
- **Evidence:** Manual test per design's "Manual UI Test Paths" — Delete
  with confirm/cancel, and a full-refresh check that other rows'
  enablement updates correctly.

### Polish

#### Task 13: Error-handling hardening and manual QA pass
- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:** Sweep both dialogs for the design's error-handling
  contract: `NetworkUnavailableError` → `error_signals.connection_lost` +
  "No connection to Rana"; `RanaFetchError` → `error_signals.fetch_error_occurred`
  + inline error; empty successful response → "No history yet" instead of a
  blank table. Run through the full "Manual UI Test Paths" list from the
  design doc.
- **Depends on:** Task 3, Task 5, Task 6, Task 8, Task 11, Task 12
- **Acceptance:** Every item in the design's "Manual UI Test Paths" section
  passes; network failure and empty-history states show the specified
  messages rather than blank/broken UI.
- **Evidence:** Manual QA checklist (design's Manual UI Test Paths) completed
  and recorded in the PR description.

#### Task 14: Stream generic history batches off the GUI thread
- **Estimate:** ~120 lines
- **Files:** `rana_qgis_plugin/utils/api.py`,
  `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:** Replace synchronous `HistoryDialog.refresh()` fetching with
  a `QgsTask` lifecycle for generic history. The task fetches one page with a
  limit of 100, maps it to plain row data, and returns its next cursor.
  Reaching the table scrollbar bottom starts the next page task. GUI-thread
  handlers create `QStandardItem` instances and append each page. Disable
  Refresh and show a loading state while a task is active. Preserve existing
  error signals and inline messages, ignore stale results, and cancel an
  active task when the dialog closes.
- **Depends on:** Task 2, Task 3
- **Acceptance:** Opening or refreshing a long generic history keeps the
  dialog/QGIS UI responsive while fetching; the first 100 rows load initially
  and later pages appear when the scrollbar reaches the bottom; Refresh is
  unavailable with a visible loading state; failures emit the same API error
  signals and inline messages; closing or refreshing again does not allow
  stale task results to overwrite current state. Schematisation fetching is
  deferred to its later dialog implementation.
- **Evidence:** Docker-based focused tests or an equivalent QGIS task test,
  plus manual verification with a long history and close-during-fetch path.
  Backend follow-up: the API can return `len(items) == limit` with
  `next == None` while more history exists; this is reported to the backend
  team and is outside the native client fix.

## Notes

- `Simulation` (New) stays a placeholder in this task list; a later feature
  will implement it (see `20260928-1752-revision-action-stubs.md` and
  `20260930-1132-rana-model-history-actions.md`).
- `Export to gpkg` and `Open in local folder` revision actions are explicitly
  out of scope (design's Legacy Migration Boundary section).
- Fetching is asynchronous through a `QgsTask` after observed long-history
  latency; see Task 14 and decision `20260930-async-history-fetch`.
- Manual UI test paths (from the design doc) apply across Tasks 3, 4, 5, 6, 7,
  8, 11, 12, 13 — see Task 13 for the consolidated pass.

## Progress

- [x] Task 1: Fetch one generic file-history page with standard errors
  - Implementation verified with Docker pytest during pairing; the proposed
    `tests/utils/test_api.py` was removed by engineer review because its
    transport mocking was not considered valuable.
- [x] Task 2: `HistoryDialog` base class
- [x] Task 3: `RanaHistoryDialog`
- [x] Task 4: Wire generic history context-menu action
  - Includes the approved shared dialog sizing: reasonable initial window
    size, content-sized first columns, and a stretching final column.
- [x] Task 5: `SchematisationRevisionHistoryDialog` skeleton
- [x] Task 6: Revision action columns (`Simulation` placeholder + `Rana Model` enablement)
- [x] Task 7: Wire schematisation file items to the revision dialog
- [x] Task 8: `Open` / `Open in web viewer` per revision row
- [x] Task 9: Expose the model-tracker job response + processes URL helper
- [x] Task 10: `Loader.delete_schematisation_revision_3di_model()`
- [x] Task 11: Wire the `Create` button
- [x] Task 12: Wire the `Delete` button
- [x] Task 13: Error-handling hardening and manual QA pass
  - Automated evidence: Docker QGIS test collection passed for the affected
    data-item, widget, loader, and utility paths.
  - Manual QA remains required for the design checklist: file/folder/root
    history, schematisation auth errors, lazy page loading, revision action
    enablement, Create/Delete flows, selected-revision opening, network
    failures, and empty-history states.
- [x] Task 14: Stream generic history pages off the GUI thread
  - Backend pagination defect remains tracked separately: a full page can be
    returned with a missing continuation cursor.
</content>
