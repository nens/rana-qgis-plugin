---
feature: feat_454_dialog
status: implemented
created: 2026-11-06
chunk_size: adaptive
total_tasks: 8
estimated_lines: 780
---

# Sync Change Summary Tasks

## Overview
Implements `design.md`: "Sync" context menu labels, and one collapsible sync dialog used
by both the on-demand sync (one kind, non-blocking) and the close and project-close routes
(modal question). Each task leaves unit tests and hooks passing.

## Task List

### Foundation

#### Task 1: Rename context menu actions to "Sync"
- **Estimate:** ~20 lines
- **Files:** `rana_qgis_plugin/layer_management/layer_tree_menu.py`, `doc/*.md`
- **Description:** Labels become "Sync style to Rana", "Sync styles to Rana", and
  "Sync data to Rana". "Save revision" is unchanged.
- **Depends on:** None
- **Acceptance:** Labels match the design on file and folder nodes.
- **Evidence:** Manual check of the context menu.

#### Task 2: Change model
- **Estimate:** ~90 lines (code plus tests)
- **Files:** `rana_qgis_plugin/utils/data_models.py`, tests
- **Description:** Add `SyncKind` and the frozen `SyncChanges` dataclass (`files`,
  `for_kind`, `merge`, `is_empty`, `file_count`).
- **Depends on:** None
- **Acceptance:** `merge` returns a new object with sorted layer names per file.
- **Evidence:** Unit tests pass.

#### Task 3: Collect changes from layers [P]
- **Estimate:** ~80 lines (code plus tests)
- **Parallel:** Can run with Task 4
- **Files:** `rana_qgis_plugin/layer_management/sync_changes.py` (new), tests
- **Description:** `collect_changes(layers, kinds, include_unknown_data=False)` returns the
  changed layer names per file, read from the layers (`layer_sync_state`,
  `has_unsynced_style`), for the requested kinds only.
- **Depends on:** Task 2
- **Acceptance:** Several layers per file, file name rather than full path, unknown data
  only with `include_unknown_data`, and only the requested kinds.
- **Evidence:** Unit tests pass.

#### Task 4: Summary and details formatting [P]
- **Estimate:** ~110 lines (code plus tests)
- **Parallel:** Can run with Task 3
- **Files:** `rana_qgis_plugin/layer_management/sync_summary.py` (new), tests
- **Description:** `build_summary`, `build_details`, `format_file_changes` and
  `build_sync_notice`, all taking `SyncChanges`. No QGIS imports.
- **Depends on:** Task 2
- **Acceptance:** Tests cover data only, style only, both, a file in both sections, a single
  file, many layers without truncation, escaping, and the notice for one and several files.
- **Evidence:** Unit tests pass.

### Core Implementation

#### Task 5: Dialog base class
- **Estimate:** ~120 lines (code plus tests)
- **Files:** `rana_qgis_plugin/layer_management/sync_prompt_dialog.py` (new), tests
- **Description:** `SyncPromptDialog` with the summary label, the "More details"
  `QgsCollapsibleGroupBox` (collapsed by default), a capped `QScrollArea`, a button row, and
  height fitting when the details are toggled.
- **Depends on:** Task 4
- **Acceptance:** Details collapsed by default; toggling shows and hides them; the scrollbar
  appears only with long content; the dialog grows and shrinks with the details.
- **Evidence:** Unit tests pass; manual check.

### Integration

#### Task 6: `CloseSyncDialog` and the close routes
- **Estimate:** ~70 lines (code plus tests)
- **Files:** `rana_qgis_plugin/layer_management/sync_prompt_dialog.py`,
  `rana_qgis_plugin/layer_management/close_sync_prompt.py`, tests
- **Description:** Modal `CloseSyncDialog` with "Sync now" and "Continue without syncing".
  The close and project-close prompts collect `SyncChanges` for both kinds and use the
  dialog. The deferred layer-removal prompt accumulates changes with `merge`.
- **Depends on:** Tasks 3, 5
- **Acceptance:** Both prompts show the summary and details; the choice decides whether
  the captured items are dispatched.
- **Evidence:** Unit tests pass; manual paths below.

#### Task 7: `OnDemandSyncDialog` and the `sync(kind)` helper
- **Estimate:** ~90 lines (code plus tests)
- **Files:** `rana_qgis_plugin/layer_management/sync_prompt_dialog.py`,
  `rana_qgis_plugin/layer_management/layer_tree_menu.py`, tests
- **Description:** Non-blocking `OnDemandSyncDialog` with an OK button, parented to the main
  window and deleted on close. One `sync(kind, groups)` helper captures the items,
  collects `SyncChanges` for the kind, dispatches, and shows the dialog.
- **Depends on:** Tasks 3, 5
- **Acceptance:** On-demand sync shows a non-blocking dialog for one kind, which stays
  until dismissed. Dispatch is not delayed.
- **Evidence:** Unit tests pass; manual paths below.

#### Task 8: Update the layer sync e2e test
- **Estimate:** ~60 lines
- **Files:** `e2e/test_layer_sync.py`
- **Description:** Answer `CloseSyncDialog` through its buttons, check the file names in the
  summary and details text, and wait for and dismiss the `OnDemandSyncDialog`.
- **Depends on:** Tasks 6, 7
- **Acceptance:** `test_dirty_tracking_and_guards` no longer waits for a `QMessageBox`.
- **Evidence:** CI e2e run.

## Notes
- Manual paths for review:
  - Context menu shows "Sync data/style to Rana".
  - Sync data on a group: the dialog names only data, does not block, stays until OK, and
    "More details" lists the files and layers. Open several at once.
  - Move and resize the dialog.
  - Close a dirty layer and a dirty project: summary visible, "More details" toggles the
    lists, scrollbar appears only with long lists.
- Decisions: `20261106-1240-sync-prompt-dialog`, `20261109-1100-sync-changes-model`,
  `20261106-1132-sync-notice-tense`, `20261106-1132-save-revision-scope`.

## Progress
- [x] Task 1: Rename context menu actions to "Sync"
- [x] Task 2: Change model
- [x] Task 3: Collect changes from layers
- [x] Task 4: Summary and details formatting
- [x] Task 5: Dialog base class
- [x] Task 6: `CloseSyncDialog` and the close routes
- [x] Task 7: `OnDemandSyncDialog` and the `sync(kind)` helper
- [x] Task 8: Update the layer sync e2e test
