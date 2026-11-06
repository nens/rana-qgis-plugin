---
feature: feat_519_dialog
status: designed
created: 2026-11-06
chunk_size: adaptive
total_tasks: 7
estimated_lines: 700
---

# Sync Selection Dialog Tasks

## Overview
Implements `design.md`: "Sync" context menu labels, and one tree dialog (`SyncDialog`) shown
before any sync starts. The on-demand route and the close, project-close and layer-removal
routes use the same dialog. Only checked files are synced. Each task leaves unit tests
passing.

## Task List

### Foundation

#### Task 1: Rename context menu actions to "Sync"
- **Estimate:** ~20 lines
- **Files:** `rana_qgis_plugin/layer_management/layer_tree_menu.py`
- **Description:** Labels become "Sync style to Rana", "Sync styles to Rana", and
  "Sync data to Rana". "Save revision" is unchanged.
- **Depends on:** None
- **Acceptance:** Labels match the design on file and folder nodes.
- **Evidence:** Manual check of the context menu (see Notes).

#### Task 2: Data model and file key
- **Estimate:** ~150 lines (code plus tests)
- **Files:** `rana_qgis_plugin/layer_management/sync_changes.py` (new),
  `tests/layer_management/test_sync_changes.py`
- **Description:** `SyncKind`, `SyncFileKey(project_id, ref)`, `file_key`, `ChangedLayer`,
  `ChangedFile`, and frozen `SyncChanges` with `from_layers`, `files`, `for_kind`, `merge`,
  `is_empty`, `file_count`.
- **Depends on:** None
- **Acceptance:** `from_layers` covers keys, file and layer icon types, style skipped without
  a descriptor, `include_unknown_data`, and only the requested kinds. `merge` returns a new
  object with the union and sorted layers. Upload item keys match tree rows.
- **Evidence:** Unit tests pass.

#### Task 3: Summary text
- **Estimate:** ~60 lines (code plus tests)
- **Files:** `rana_qgis_plugin/layer_management/sync_summary.py`,
  `tests/layer_management/test_sync_summary.py`
- **Description:** `build_summary(changes)` only. No QGIS imports.
- **Depends on:** Task 2
- **Acceptance:** Data only, style only, both, single file, many files, counts per project.
- **Evidence:** Unit tests pass.

### Core Implementation

#### Task 4: `SyncDialog` tree
- **Estimate:** ~180 lines (code plus tests)
- **Files:** `rana_qgis_plugin/layer_management/sync_prompt_dialog.py`,
  `tests/layer_management/test_sync_dialog.py`
- **Description:** Header-less, fully expanded tree of sections, projects, folders, files and
  layers. Sections, projects and folders are auto-tristate; files are checkable; layers are
  display only. `selected(kind)` returns checked file keys. Confirm is disabled when nothing
  is checked.
- **Depends on:** Tasks 2, 3
- **Acceptance:** All checked by default; unchecking a file or folder updates `selected`;
  partial state on parents; nesting by path; confirm disabled when nothing is checked.
- **Evidence:** Offscreen unit tests pass; manual check of both themes.

### Integration

#### Task 5: On-demand route
- **Estimate:** ~70 lines
- **Files:** `rana_qgis_plugin/layer_management/layer_tree_menu.py`
- **Description:** `sync(kind, groups)` captures upload items for the one kind, shows
  `SyncDialog` modally (no section roots, project names fetched) with "Continue sync" and
  "Cancel sync", and dispatches only the items
  whose `file_key` is selected. Unselected items are dropped without discard.
- **Depends on:** Tasks 2, 4
- **Acceptance:** Only the chosen kind is named; the dialog is modal; cancel dispatches nothing.
- **Evidence:** Covered by the E2E test (CI). No unit test for `sync(kind)` yet (see design).

#### Task 6: Close, project-close and layer-removal routes
- **Estimate:** ~90 lines
- **Files:** `rana_qgis_plugin/layer_management/close_sync_prompt.py`
- **Description:** `SyncPromptAction.prompt_and_dispatch` shows `SyncDialog` with "Unsynced
  changes", "Sync changes now" and "Continue without syncing". It dispatches the checked items
  and passes unchecked style snapshots, and all of them on cancel, to `discard_layer_sources`.
  The layer-removal prompt accumulates changes with `merge`.
- **Depends on:** Tasks 2, 4
- **Acceptance:** Only checked files dispatch; cancel and unchecked style snapshots are
  released; the two routes keep separate filters.
- **Evidence:** `test_project_close_sync_prompt.py` and `test_layer_removal_sync_prompt.py`
  pass.

#### Task 7: Layer sync e2e test and cleanup
- **Estimate:** ~80 lines
- **Files:** `e2e/test_layer_sync.py`, removed code in `layer_management/`
- **Description:** Answer `SyncDialog` through its buttons. The on-demand handler clicks
  "Continue sync" before each trigger, because the dialog is modal. Read the file names from
  the tree rows. Remove `CloseSyncDialog`, `OnDemandSyncDialog`, `QgsCollapsibleGroupBox`,
  height fitting, `build_details`, `build_sync_notice`, `format_file_changes`, `file_labels`,
  `collect_changes`, and the post-dispatch notice. No new E2E tests.
- **Depends on:** Tasks 5, 6
- **Acceptance:** No references to removed names in `rana_qgis_plugin/layer_management` or
  `tests/`. The E2E file parses. E2E is not run locally.
- **Evidence:** Full unit suite passes (581 passed, 2 skipped). E2E: CI run pending.

## Notes
- Manual paths for review:
  - Context menu shows "Sync data/style to Rana".
  - On-demand data sync and style sync: the dialog names only the chosen kind, is modal, and
    unchecked files are not synced.
  - Close and project close with unsynced changes: the tree lists the files, and confirm syncs
    only checked files.
  - Remove a dirty layer and a dirty group: the same dialog appears once.
  - Cancel on both routes: nothing is synced.
  - Confirm with some files unchecked.
  - Light and dark themes: the tree background matches the dialog.
- Decisions: `20261106-1240-sync-prompt-dialog`, `20261109-1100-sync-changes-model`,
  `20261111-1200-sync-selection-flow`, `20261106-1132-save-revision-scope`.
- Review feedback (2026-11-11), done in tasks 2-6: no duplicate layers on close, no section
  roots and a count-only summary on the on-demand route and project names from the API.
- Open point: `scripts/render_sync_prompt.py` is out of date and not changed here.

## Progress
- [x] Task 1: Rename context menu actions to "Sync"
- [x] Task 2: Data model and file key
- [x] Task 3: Summary text
- [x] Task 4: `SyncDialog` tree
- [x] Task 5: On-demand route
- [x] Task 6: Close, project-close and layer-removal routes
- [x] Task 7: Layer sync e2e test and cleanup
