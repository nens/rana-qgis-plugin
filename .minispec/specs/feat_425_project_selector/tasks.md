---
feature: project-visibility-selection
branch: feat_425_project_selector
status: complete
created: 2026-08-03
chunk_size: adaptive
total_tasks: 4
estimated_lines: 335
---

# Project Visibility Selection — Tasks

## Overview

Let users control which projects appear in `RanaRootDataItem` via per-project hiding and a bulk selection dialog. State is stored as a per-`(base_url, tenant_id)` blocklist in a JSON file.

## Task List

### Foundation

#### Task 1: Project visibility storage layer
- **Estimate:** ~50 lines implementation + ~40 lines tests
- **Files:**
  - `rana_qgis_plugin/utils/project_visibility.py` (new)
  - `tests/utils/test_project_visibility.py` (new)
- **Description:** Pure Python module for reading and writing the hidden projects blocklist. No UI or QGIS dependencies (use `pathlib.Path` directly, accept file path as argument in helpers to keep it testable).
  - `hidden_projects_file() -> Path` — `{qgisSettingsDirPath}/rana/hidden_projects.json`
  - `get_hidden_projects(base_url, tenant_id) -> set[str]`
  - `set_hidden_projects(base_url, tenant_id, hidden_ids: set[str]) -> None` — atomic write
  - `hide_project(base_url, tenant_id, project_id) -> None`
  - `show_project(base_url, tenant_id, project_id) -> None`
- **Depends on:** None
- **Acceptance:** Unit tests cover: read from missing file → empty set; write/read roundtrip; two different scopes don't interfere; atomic write leaves no `.tmp` on success
- **Evidence:** `pytest tests/utils/test_project_visibility.py` passes

### Core Implementation

#### Task 2: Filter in `createChildren()` + "Don't show this project" action [P]
- **Estimate:** ~30 lines
- **Parallel:** Can run with Task 3
- **Files:**
  - `rana_qgis_plugin/data_items/rana_item.py`
  - `rana_qgis_plugin/data_items/project_item.py`
- **Description:**
  - In `RanaRootDataItem.createChildren()`: after fetching projects, load hidden set via `get_hidden_projects(base_url(), get_tenant_id())` and filter the items list before creating `RanaProjectDataItem` children
  - In `RanaProjectDataItem.actions()`: add "Don't show this project" `QAction` that calls `hide_project(base_url(), get_tenant_id(), self._project_id)` then `self.parent().refresh()`
- **Depends on:** Task 1
- **Acceptance:** Manual test — right-click a project → "Don't show this project" → disappears from browser; restart QGIS → still hidden
- **Evidence:** Manual test passes

#### Task 3: `ProjectsSelectionDialog` [P]
- **Estimate:** ~200 lines
- **Parallel:** Can run with Task 2
- **Files:**
  - `rana_qgis_plugin/widgets/projects_selection_dialog.py` (new)
- **Description:** Fork `legacy/widgets/projects_browser.py` and adapt:
  - Wrap in `QDialog` (not `QWidget`)
  - Remove pagination — load all projects at once
  - Remove "Open project" context menu
  - Add checkbox via `Qt.CheckStateRole` on name column
  - Add "Check All" and "Uncheck All" toolbar buttons
  - Shift+click range toggle on checkbox column
  - Constructor receives current hidden set; pre-checks visible projects
  - On OK: calls `set_hidden_projects()` with updated set
  - Port avatar delegate (`ContributorAvatarsDelegate`) from legacy
  - Keep `FilterBar` with text search and contributor combo
- **Depends on:** Task 1
- **Acceptance:** Dialog opens showing all projects; filtering works; check/uncheck persists after OK; avatars display
- **Evidence:** Manual test passes (see Task 4)

### Integration

#### Task 4: "Select projects" action on `RanaRootDataItem`
- **Estimate:** ~15 lines
- **Files:**
  - `rana_qgis_plugin/data_items/rana_item.py`
- **Description:** Add "Select projects" `QAction` to `RanaRootDataItem.actions()` (authenticated state only). Action instantiates `ProjectsSelectionDialog(self.communication)`, calls `exec()`, and on accepted calls `self.refresh()`.
- **Depends on:** Task 3
- **Acceptance:** Manual test — right-click Rana root → "Select projects" → dialog opens with all projects; uncheck some → OK → browser updates; reopen dialog → unchecked projects still unchecked; switch tenant → independent hidden set
- **Evidence:** Manual test passes

## Notes

- No unit tests for Tasks 2 and 4 — QGIS data item integration requires heavy mocking that would test the mock rather than the code. Manual test paths cover these.
- Stale hidden IDs (deleted projects) are silently ignored — they remain in the JSON but never match a fetched project. No cleanup needed.
- `createChildren()` runs in a background thread. File reads in `get_hidden_projects()` are safe since writes are atomic (rename).

## Progress

- [x] Task 1: Project visibility storage layer
- [x] Task 2: Filter in `createChildren()` + "Don't show this project" action
- [x] Task 3: `ProjectsSelectionDialog`
- [x] Task 4: "Select projects" action on `RanaRootDataItem`
