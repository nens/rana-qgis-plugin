# Design: Group FileView Buttons Under Ellipsis Menu

**Branch**: `feat_4165_group_file_view_buttons`  
**Created**: 2026-05-12  
**Status**: Planned  

---

## Overview

Move several FileView actions from dedicated buttons into an ellipsis (...) dropdown menu. The ellipsis button is added as the rightmost button in the top row of action buttons. Additionally, add a new "Copy WMS URL" action for scenarios.

---

## Ellipsis Menu Contents by File Type

| File type | Menu items |
|---|---|
| All files | Rename, Delete |
| Non-schematisation files | + History (renamed from "View all Revisions") |
| Schematisation | + Export GeoPackage |
| Scenarios (3Di) | + Copy WMS URL |

## Other Changes

- `btn_export_gpkg` is removed from row 2 (moved into ellipsis menu)
- `btn_show_revisions` stays in row 2, but only shown for schematisations (was shown for all files)
- The ellipsis button uses the existing `ellipsis_icon` from `rana_qgis_plugin.icons`

---

## User Stories

### Story 1 — Ellipsis menu with common actions (P1)

User selects any file and sees an ellipsis button (rightmost in top row). Clicking it shows a dropdown with Rename and Delete.

**Acceptance scenarios:**
1. **Given** any file is selected, **When** user clicks the ellipsis, **Then** a menu shows Rename and Delete
2. **Given** the menu is open, **When** user clicks Rename, **Then** the rename flow is triggered (same as current button)
3. **Given** the menu is open, **When** user clicks Delete, **Then** the delete flow is triggered (same as current button)

### Story 2 — History for non-schematisation files (P1)

Non-schematisation files get a "History" item in the ellipsis menu (replacing the current "View all Revisions" button in row 2).

**Acceptance scenarios:**
1. **Given** a non-schematisation file is selected, **When** user clicks the ellipsis, **Then** menu includes "History"
2. **Given** a schematisation is selected, **When** user clicks the ellipsis, **Then** menu does NOT include "History"

### Story 3 — Export GeoPackage for schematisations (P1)

The "Export GeoPackage" button moves from row 2 into the ellipsis menu for schematisations.

**Acceptance scenarios:**
1. **Given** a schematisation is selected, **When** user clicks the ellipsis, **Then** menu includes "Export to GeoPackage"
2. **Given** a non-schematisation file is selected, **When** user clicks the ellipsis, **Then** menu does NOT include "Export to GeoPackage"
3. The `btn_export_gpkg` button no longer exists in row 2

### Story 4 — View all Revisions stays in row 2 for schematisations only (P1)

`btn_show_revisions` remains in row 2 but is only visible when a schematisation is selected.

**Acceptance scenarios:**
1. **Given** a schematisation is selected, **Then** "View all Revisions" button is visible in row 2
2. **Given** a non-schematisation file is selected, **Then** "View all Revisions" button is hidden

### Story 5 — Copy WMS URL for scenarios (P2)

Scenarios with WMS support get a "Copy WMS URL" item in the ellipsis menu.

**Acceptance scenarios:**
1. **Given** a 3Di scenario is selected, **When** user clicks the ellipsis, **Then** menu includes "Copy WMS URL"
2. **Given** user clicks "Copy WMS URL", **Then** the WMS base URL is copied to the clipboard
3. **Given** a non-scenario file is selected, **Then** "Copy WMS URL" does NOT appear in the ellipsis menu

---

## Implementation Notes

### Ellipsis Button & Menu

- Add a `QPushButton` with `ellipsis_icon` as the rightmost button in the top action button row
- Attach a `QMenu` to it, populated dynamically based on the selected file type
- Follow the pattern from `breadcrumbs.py` (lines 62-73) for the button/menu setup

### Copy WMS URL

- Retrieve WMS URL via `get_tenant_file_descriptor(file["descriptor_id"])`, extract `link["href"]` where `link["rel"] == "wms"` (same path as `layer_manager.py:252-266`)
- Copy to clipboard via `QApplication.clipboard().setText(url)`

### Buttons to Remove from Current Layout

- Rename button — moves to ellipsis menu
- Delete button — moves to ellipsis menu
- `btn_export_gpkg` — moves to ellipsis menu
- "View all Revisions" button in top row (if it exists there) — becomes "History" in ellipsis for non-schematisations

### Button Visibility Changes

- `btn_show_revisions` (row 2): only shown for schematisations (currently shown for all)

## Manual Testing

- Select each file type (schematisation, scenario, raster, vector) and verify the ellipsis menu shows the correct items
- Verify Rename, Delete, History, Export GeoPackage all trigger the same flows as before
- Verify Copy WMS URL copies the correct URL for a 3Di scenario
- Verify `btn_show_revisions` only appears for schematisations
- Verify `btn_export_gpkg` no longer appears in row 2
