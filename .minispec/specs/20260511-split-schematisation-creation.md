# Design: Split Schematisation Creation into Two Flows

**Branch**: `feat_4224_upload_existing_`  
**Created**: 2026-05-11  
**Status**: Planned  
**Decisions**: `20260511-1413-split-schematisation-wizard.md`

---

## Overview

The current "New schematisation" action combines two distinct user intents in a single wizard: creating a schematisation from scratch, and uploading an existing GeoPackage as a new schematisation. These are split into two separate UI entry points, each with a dedicated wizard class.

---

## User Stories

### Story 1 — Create new schematisation from scratch (P1)

User clicks "New schematisation" in the files browser. A wizard opens asking for name, description, tags, and organisation. The wizard then guides the user through explanation and settings pages. A new empty GeoPackage is created.

**Acceptance scenarios:**
1. **Given** the files browser is open, **When** the user clicks "New schematisation", **Then** a wizard opens with name/description/tags/org fields and no GeoPackage selector
2. **Given** the wizard is complete, **When** the user clicks "Create schematisation", **Then** a new schematisation and empty GeoPackage are created

---

### Story 2 — Upload existing schematisation from GeoPackage (P2)

User clicks "Upload existing schematisation" in the files browser. A file picker appears immediately (before the wizard). After selecting a `.gpkg` or `.sqlite` file, a wizard opens asking for name, description, tags, and organisation. The existing GeoPackage is copied into the new schematisation.

**Acceptance scenarios:**
1. **Given** the files browser is open, **When** the user clicks "Upload existing schematisation", **Then** a file picker opens immediately
2. **Given** the user cancels the file picker, **Then** nothing further happens and the browser re-enables
3. **Given** the user selects a valid gpkg file, **When** the wizard completes, **Then** the existing GeoPackage (and any rasters) are copied into the new schematisation
4. **Given** the selected gpkg has missing rasters, **Then** a warning is shown and creation is aborted

---

## Design Decisions

See `.minispec/knowledge/decisions/20260511-1413-split-schematisation-wizard.md`.

---

## Components

### `NewSchematisationWizard` (modified)
- Pages: Name → Explain → Settings (unchanged)
- `SchematisationNamePage` instantiated with `show_gpkg_selector=False`
- `create_schematisation()` always calls `create_new_schematisation()` — no branching
- No change to class name; existing callers unaffected

### `UploadExistingSchematisationWizard` (new)
- Constructor takes `gpkg_path` in addition to standard args
- Single page: Name page only (it is the final page)
- `SchematisationNamePage` instantiated with `show_gpkg_selector=False`
- `create_schematisation()` calls `create_schematisation_from_geopackage(gpkg_path)`

### `_create_schematisation_base()` (new module-level helper)
- Extracted from the shared setup in both creation methods
- Creates schematisation remotely via API and sets up `LocalSchematisation`
- Returns `(schematisation, local_schematisation, wip_revision)`

### `get_paths_from_geopackage()` (promoted to module-level function)
- Currently a `@staticmethod` on `NewSchematisationWizard`; moved to module level
- Still callable from `loader.py` — import changes accordingly

### `SchematisationNamePage` / `SchematisationNameWidget` (modified)
- GeoPackage section removed entirely: label, radio buttons, path field, browse button, `browse_existing_geopackage()` method
- `isComplete()` simplified to only check `schematisation_name`
- `update_pages_order()` and `nextId()` removed (no gpkg branching)
- Fields `from_geopackage` and `geopackage_path` removed

### `files_browser.py` (modified)
- New button: `btn_upload_existing_schematisation` ("Upload existing schematisation")
- Visibility follows same `has_3di_authcfg()` check as existing schematisation buttons

### `rana_browser.py` (modified)
- New signal: `upload_existing_schematisation_selected = pyqtSignal(dict, dict)`
- `btn_upload_existing_schematisation.clicked` connected to emit this signal

### `loader.py` (modified)
- New slot: `upload_existing_schematisation_to_rana(project, selected_item)`
- Shows file picker before wizard; cancelling picker aborts the flow
- Instantiates `UploadExistingSchematisationWizard` with the selected `gpkg_path`
- Post-wizard flow identical to existing `upload_new_schematisation_to_rana`

### `rana_qgis_plugin.py` (modified)
- New signal/slot connection for `upload_existing_schematisation_selected`

---

## Open Questions

- None — scope is clear and bounded.
