---
feature: browser-filters
status: complete
created: 2026-05-04
chunk_size: medium
total_tasks: 5
estimated_lines: ~450
---

# Browser Filters Tasks

## Overview

Add a shared `FilterBar` widget and connect it to all four browser widgets
(ProjectsBrowser, ProcessesBrowser, FilesBrowser, PublicationsBrowser).
Filtering is client-side. Full design at `.minispec/specs/2026-05-04-browser-filters-design.md`.
Implementation plan at `docs/superpowers/plans/2026-05-04-browser-filters.md`.

---

## Task List

### Foundation

#### Task 1: Create `FilterBar` widget
- **Estimate:** ~70 lines
- **Files:**
  - Create: `rana_qgis_plugin/widgets/filter_bar.py`
- **Description:** New `FilterBar(QWidget)` with `TextFilterConfig` and `ComboFilterConfig`
  dataclasses. Accepts a list of filter configs, lays them out horizontally with a refresh
  button. Emits `filters_changed(dict)`. Uses `QgsCheckableComboBox` for multi-select combos.
  Exposes `get_filters()`, `set_combo_items()`, `update_combo_avatar()`.
- **Depends on:** None
- **Acceptance:** Plugin loads without import errors; `pytest tests/` passes.

#### Task 2: Connect `FilterBar` to `ProjectsBrowser`
- **Estimate:** ~80 lines changed
- **Files:**
  - Modify: `rana_qgis_plugin/widgets/projects_browser.py`
- **Description:** Replace `self.projects_search`, `self.contributor_filter`, and
  `self.refresh_btn` with a `FilterBar` in `setup_ui`. Replace `filter_active`,
  `filter_projects()`, `get_projects_filtered_by_name()`, `get_projects_filtered_by_contributor()`
  with `_apply_filters(filters: dict)` handling name, who (multi-select), and status.
  Update `populate_contributors()` to use `filter_bar.set_combo_items("who", ...)`.
  Update `update_avatar()` to use `filter_bar.update_combo_avatar("who", ...)`.
  Remove `_on_contributor_filter_text_changed`. Update imports.
- **Depends on:** Task 1
- **Acceptance:** `pytest tests/` passes; manual: name search, multi-select who, status filter
  (active/archived), refresh button, and pagination all work correctly.

### Core Implementation

#### Task 3: Connect `FilterBar` to `ProcessesBrowser` — UI + filter logic
- **Estimate:** ~70 lines added/changed
- **Files:**
  - Modify: `rana_qgis_plugin/widgets/processes_browser.py`
- **Description:** Add `FilterBar` (name + who + status) to `setup_ui`. Store `JobData` on
  `name_item` via `UserRole` in `add_item`. Add `_apply_filters()` using `setRowHidden`.
  Add `_reapply_filters()` and `_repopulate_who_combo()`. Call both after `add_item` and
  after `update_state_for_job`. Clear who combo in `update_project`.
- **Depends on:** Task 1
- **Acceptance:** `pytest tests/` passes; manual: name/who/status filters work; new jobs
  arriving via websocket respect active filters.

#### Task 4: Connect `FilterBar` to `FilesBrowser` — UI + filter logic
- **Estimate:** ~60 lines added/changed
- **Files:**
  - Modify: `rana_qgis_plugin/widgets/files_browser.py`
- **Description:** Add `FilterBar` (name + type) to `setup_ui`. Add `_apply_filters()` using
  `setRowHidden` — directories are only filtered by name, never by type. Add
  `_populate_type_combo()` that reads `data_type` from loaded file dicts (`null` → "unknown").
  Call both at end of `fetch_and_populate`.
- **Depends on:** Task 1
- **Acceptance:** `pytest tests/` passes; manual: name filter works on filenames; type combo
  is populated from loaded files; "Unknown" appears for unidentified files; navigating into a
  subdirectory repopulates the type combo; directories are never hidden by type filter.

#### Task 5: Connect `FilterBar` to `PublicationsBrowser` — UI + filter logic
- **Estimate:** ~60 lines added/changed
- **Files:**
  - Modify: `rana_qgis_plugin/widgets/publications_browser.py`
- **Description:** Add `FilterBar` (name + who) to `setup_ui`. Add `_apply_filters()` using
  `setRowHidden`. Add `_reapply_filters()` and `_repopulate_who_combo()`. Call both at end of
  `add_items` and `update_item`. Clear who combo in `update_project`.
- **Depends on:** Task 1
- **Acceptance:** `pytest tests/` passes; manual: name and who filters work; new publications
  arriving via websocket respect active filters.

---

## Notes

- ProcessesBrowser and PublicationsBrowser have no standalone refresh; `FilterBar` refresh
  button uses `lambda: None` for these.
- ProjectsBrowser keeps `filtered_projects` + `populate_projects()` pattern due to pagination.
  Tasks 4–6 use `setRowHidden()` instead.
- `QgsCheckableComboBox` is from `qgis.gui` — no custom widget needed for multi-select.
- Avatar icons work natively via `addItem(QIcon, label, userData)` on `QgsCheckableComboBox`.
- Detailed implementation steps (with code) are in
  `docs/superpowers/plans/2026-05-04-browser-filters.md`.

## Deferred

- Pagination removal (simplifies ProjectsBrowser but is a separate change).
- Filter state persistence between sessions.

---

## Progress

- [ ] Task 1: Create `FilterBar` widget + tests
- [ ] Task 2: Connect `FilterBar` to `ProjectsBrowser`
- [ ] Task 3: Connect `FilterBar` to `ProcessesBrowser`
- [ ] Task 4: Connect `FilterBar` to `FilesBrowser`
- [ ] Task 5: Connect `FilterBar` to `PublicationsBrowser`
