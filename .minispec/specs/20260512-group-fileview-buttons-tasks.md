---
feature: group-fileview-buttons
status: planned
created: 2026-05-12
chunk_size: medium
total_tasks: 4
estimated_lines: 170
---

# Group FileView Buttons Under Ellipsis Menu — Tasks

## Overview
Move several FileView actions into an ellipsis dropdown menu and add a new Copy WMS URL action for scenarios. Steps are ordered so new functionality can be tested before reorganizing the UI.

## Task List

### Step 1: New FileAction entries

#### Task 1: Add COPY_WMS_URL and HISTORY to FileAction
- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/widgets/utils_file_action.py`
- **Description:**
  - Add `COPY_WMS_URL` and `HISTORY` to `FileAction` enum
  - Add `copy_wms_url_requested` signal to `FileActionSignals`
  - Update `get_file_actions_by_data_type()`: add `HISTORY` for non-schematisation files, `COPY_WMS_URL` for scenarios
- **Depends on:** None
- **Acceptance:** Unit tests pass. New actions appear in `get_file_actions()` output for the correct file types.

### Step 2: History and Revisions visibility

#### Task 2: Wire History action and restrict Revisions button
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/widgets/file_view.py`
- **Description:**
  - Wire `HISTORY` action to the same revisions signal/flow as "View all Revisions"
  - Restrict `btn_show_revisions` (row 2) to schematisations only
- **Depends on:** Task 1
- **Acceptance:** Non-schematisation files show a History button (top row). `btn_show_revisions` only visible for schematisations. History triggers the revisions view.

### Step 3: Copy WMS URL

#### Task 3: Implement Copy WMS URL handler
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/widgets/rana_browser.py`, `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/rana_qgis_plugin.py`
- **Description:**
  - Wire `copy_wms_url_requested` signal through `rana_browser.py` (relay pattern)
  - Add handler that calls `get_tenant_file_descriptor()`, extracts WMS `href`, copies to clipboard
  - Connect signal in `rana_qgis_plugin.py`
- **Depends on:** Task 1
- **Acceptance:** Clicking Copy WMS URL on a 3Di scenario copies the WMS base URL to the clipboard.

### Step 4: Ellipsis button, move buttons, context menu

#### Task 4: Create ellipsis menu and reorganize buttons
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/widgets/file_view.py`, `rana_qgis_plugin/widgets/files_browser.py`
- **Description:**
  - Create ellipsis `QPushButton` (rightmost, top row) with `QMenu`
  - Populate menu dynamically per file type (Rename, Delete, History, Export GeoPackage, Copy WMS URL)
  - Remove Rename, Delete from top row buttons
  - Remove `btn_export_gpkg` from row 2
  - Add `COPY_WMS_URL` to right-click context menu in `files_browser.py`
- **Depends on:** Tasks 2, 3
- **Acceptance:** Ellipsis menu shows correct items per file type. Removed buttons no longer appear. Context menu includes Copy WMS URL for scenarios.

## Notes
- Tasks 2 and 3 can run in parallel after Task 1
- Task 4 depends on both 2 and 3
- History in the ellipsis menu is NOT added to the right-click context menu — only Revisions appears there (for schematisations)

## Progress
- [x] Task 1: Add COPY_WMS_URL and HISTORY to FileAction
- [x] Task 2: Wire History action and restrict Revisions button
- [x] Task 3: Implement Copy WMS URL handler
- [x] Task 4: Create ellipsis menu and reorganize buttons
