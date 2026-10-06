---
feature: feat_4224_upload_existing_
status: planned
created: 2026-05-11
chunk_size: medium
total_tasks: 5
estimated_lines: 210
---

# Split Schematisation Creation Tasks

## Overview

Split the existing combined "New schematisation" wizard into two separate entry points and wizard classes: one for creating a schematisation from scratch, one for uploading an existing GeoPackage.

## Task List

### Foundation

#### Task 1: Clean up `SchematisationNamePage`
- **Estimate:** ~50 lines removed/changed
- **Files:** `rana_qgis_plugin/widgets/new_wizard_pages/name.py`
- **Description:** Delete the entire GeoPackage section from `SchematisationNameWidget` (label, radio buttons, path field, browse button, `browse_existing_geopackage()` method). Remove unused imports (`QRadioButton`, `QToolButton`). Simplify `SchematisationNamePage`: remove `from_geopackage`/`geopackage_path` field registrations, remove `update_pages_order()`, simplify `isComplete()` and `nextId()`.
- **Depends on:** None
- **Acceptance:** `SchematisationNamePage` renders only name, description, tags, organisation fields. No GeoPackage UI present.

#### Task 2: Extract shared helpers in `schematisation_new_wizard.py`
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/widgets/schematisation_new_wizard.py`
- **Description:** Extract `_create_schematisation_base()` as a module-level helper function from the duplicated API + `LocalSchematisation` setup shared by both creation methods. Promote `get_paths_from_geopackage` from `@staticmethod` to a module-level function.
- **Depends on:** Task 1
- **Acceptance:** Both existing creation methods use `_create_schematisation_base()`. `get_paths_from_geopackage` is importable at module level.

#### Task 3: Simplify `NewSchematisationWizard`, add `UploadExistingSchematisationWizard`
- **Estimate:** ~50 lines
- **Files:** `rana_qgis_plugin/widgets/schematisation_new_wizard.py`
- **Description:** Simplify `NewSchematisationWizard`: remove `create_schematisation_from_geopackage`, remove branching in `create_schematisation()`. Add new `UploadExistingSchematisationWizard` class: takes `gpkg_path` in constructor, single Name page (set as final page), uses `_create_schematisation_base()` then copies gpkg and rasters.
- **Depends on:** Task 2
- **Acceptance:** `NewSchematisationWizard` has no gpkg branching. `UploadExistingSchematisationWizard` can be instantiated with a path and completes the upload flow.

### Integration

#### Task 4: Add UI button and signal [P]
- **Estimate:** ~25 lines
- **Parallel:** Can run with Task 5
- **Files:** `rana_qgis_plugin/widgets/files_browser.py`, `rana_qgis_plugin/widgets/rana_browser.py`
- **Description:** Add `btn_upload_existing_schematisation` ("Upload existing schematisation") to `files_browser.py` with same visibility logic as existing schematisation buttons. Add signal `upload_existing_schematisation_selected = pyqtSignal(dict, dict)` to `rana_browser.py` and connect the button to emit it.
- **Depends on:** Task 3
- **Acceptance:** "Upload existing schematisation" button appears in files browser alongside existing buttons.

#### Task 5: Wire up loader slot and plugin connections [P]
- **Estimate:** ~45 lines
- **Parallel:** Can run with Task 4
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/rana_qgis_plugin.py`
- **Description:** Add `upload_existing_schematisation_to_rana` slot to `loader.py`: show file picker first, cancel if no file selected, then instantiate `UploadExistingSchematisationWizard` and run the same post-wizard flow as `upload_new_schematisation_to_rana`. Update import of `get_paths_from_geopackage` (now module-level). Connect new signal → slot in `rana_qgis_plugin.py`.
- **Depends on:** Task 3
- **Acceptance:** Clicking "Upload existing schematisation" shows file picker, then wizard, then completes schematisation creation. Cancelling file picker aborts cleanly.

## Notes
- `get_paths_from_geopackage` is called on the wizard instance in `loader.py` (line 1588); after Task 2 this becomes a direct import
- The `show_gpkg_selector` flag approach was explicitly rejected — gpkg UI is deleted, not hidden
- Manual testing paths: "New schematisation" full flow; "Upload existing schematisation" full flow; cancel at file picker; cancel at wizard

## Progress
- [x] Task 1: Clean up `SchematisationNamePage`
- [x] Task 2: Extract shared helpers
- [x] Task 3: Simplify `NewSchematisationWizard`, add `UploadExistingSchematisationWizard`
- [x] Task 4: Add UI button and signal
- [x] Task 5: Wire up loader slot and plugin connections
