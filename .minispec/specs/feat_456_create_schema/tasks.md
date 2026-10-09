---
feature: feat_456_create_schema
status: planned
created: 2026-10-08
chunk_size: adaptive
total_tasks: 11
estimated_lines: 1250
---

# Add Schematisation Tasks

## Overview

Implement the three add-schematisation routes: import a selected HCC revision,
upload an existing `.gpkg`/`.sqlite` schematisation, and create a new
schematisation from scratch. Add the route submenu to the Files root and folder
items. Port copies of the legacy wizard/page modules to Qt 6 and integrate them
through the existing loader and current `SchematisationUploadTask`.

The existing legacy files are reference/source files. Copy them into the
current `rana_qgis_plugin/widgets/` area before modifying the port; leave
`rana_qgis_plugin/legacy/` untouched. Make loader changes in the existing
`rana_qgis_plugin/loader.py`.

Two different migration approaches apply here:

- **Wizard/dialog content** (`schematisation_new_wizard.py`,
  `new_wizard_pages/*`): this is **migrated** — copy the legacy file(s), then
  adapt for Qt 6 and current-plugin conventions. Behavior implemented inside
  the wizard (including the local name-availability check) should carry over
  with its copy, not be reimplemented separately.
- **Loader-arranged orchestration** (registration, initial-revision upload,
  Browser refresh): the current `loader.py` has a different architecture
  (QgsTask-based, no legacy signals/communication object), so this cannot be
  copied as-is. It must be **re-implemented** in the existing `loader.py`,
  using the legacy `loader.py` (e.g. `save_initial_revision()`,
  `_finish_schematisation_upload()`) as behavioral reference only.

## Task List

### Foundation and Browser entry

#### Task 1: Add the Add schematisation submenu to folder items
- **Estimate:** ~70 lines
- **Files:** `rana_qgis_plugin/data_items/file_actions.py`, `rana_qgis_plugin/data_items/folder_item.py`, `tests/data_items/test_file_actions.py`, new `tests/data_items/test_folder_item.py` (no direct test of `RanaFolderDataItem.actions()` exists yet; folder-item behavior is currently only covered indirectly via `tests/data_items/test_gui_provider.py`)
- **Description:** Add one Add schematisation parent action with Import from HCC, Upload existing, and From scratch submenu items on the Files root and every folder. Pass the project and invoking `folder_path` to the selected route. Empty root path targets project root.
- **Depends on:** None
- **Acceptance:** The menu exposes all three routes on root and nested folders and passes the correct target folder.
- **Evidence:** Focused action/folder tests pass, including root and nested target paths.

### HCC import

#### Task 2: Port upstream HCC revision selection behavior into current UI
- **Estimate:** ~100 lines
- **Files:** Current schematisation selection dialog under `rana_qgis_plugin/widgets/`, existing `rana_qgis_plugin/loader.py`, relevant widget/loader tests
- **Description:** Implement the upstream HCC import flow in current code (it is not yet implemented on this branch): select a schematisation, fetch and display its revisions newest first, preselect the newest revision, and disallow confirmation without valid selections. Reuse current `ThreediCalls` APIs and Qt 6/QGIS UI imports; do not add another loader module.
- **Depends on:** Task 1
- **Acceptance:** Schematisation selection loads revisions, newest is selected by default, and empty/error states are handled without attempting a copy.
- **Evidence:** Focused tests cover revision order/default selection, no revisions, and fetch failure.

#### Task 3: Copy the selected HCC revision and refresh the Browser
- **Estimate:** ~80 lines
- **Files:** Existing `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/utils/api.py`, relevant tests
- **Description:** Update the existing copy API wrapper and loader flow to send `schematisation_id`, `revision_id`, and the upstream destination path including the selected revision-number suffix under the invoking folder. Surface Rana errors and refresh the Browser only after successful copy. Confirm path formatting against upstream commit `5a603a5cce555e1ee17c132aab9edc6191053d16` while implementing this HCC task.
- **Depends on:** Task 2
- **Acceptance:** Exact selected revision and folder-specific destination are passed to Rana; failures do not appear successful or refresh as success.
- **Evidence:** API payload/path tests plus loader success/failure refresh tests pass.

### Shared upload/create wizard foundation

#### Task 4: Copy legacy wizard/page modules and port shared metadata UI to Qt 6
- **Estimate:** ~130 lines
- **Files:** Copy `rana_qgis_plugin/legacy/widgets/schematisation_new_wizard.py` and `rana_qgis_plugin/legacy/widgets/new_wizard_pages/{name.py,explain.py,settings.py}` into current `rana_qgis_plugin/widgets/` modules; tests under `tests/widgets/`
- **Description:** Preserve the legacy originals. Port the shared name, optional description, and organisation/owner UI for Upload existing and From scratch using QGIS Qt imports. Hide organisation selection when there is only one choice. Migrate the legacy `_check_name_available()` local name-conflict check (currently in the wizard, not the loader) into the copied module(s), so duplicate local names are rejected before any Rana registration is attempted. Establish a small shared schematisation-setup helper consistent with the accepted separate-flow decision.
- **Depends on:** None
- **Acceptance:** Current modules are copied (not imported from `legacy`), use Qt 6-compatible QGIS Qt APIs, expose the agreed shared metadata values to both routes, and reject a locally-duplicate schematisation name before registration is attempted.
- **Evidence:** Widget tests cover required name, optional description, one/multiple organisation behavior, and the local name-conflict rejection; import/lint checks confirm no direct PyQt imports.

#### Task 5: Port Upload existing input validation and local preparation
- **Estimate:** ~150 lines
- **Files:** Copied `rana_qgis_plugin/widgets/schematisation_new_wizard.py` and relevant copied page/helper modules, current schema/raster helpers where suitable, tests under `tests/widgets/` or `tests/simulation/`
- **Description:** Port the existing-file flow for `.gpkg` and `.sqlite`: validate schema, normalize SQLite when required, extract referenced raster paths, copy the source content into local schematisation structure, and block preparation when any referenced raster is missing. Preserve the legacy user-facing workflow while adapting Qt 6 and current-plugin conventions.
- **Depends on:** Task 4
- **Acceptance:** Supported input formats prepare valid local content; invalid schema and missing referenced raster stop the route before remote upload.
- **Evidence:** Focused tests exercise `.gpkg`, `.sqlite`, invalid-schema, and missing-raster cases using realistic fixtures where available.

#### Task 6: Reuse SchematisationUploadTask for initial revision upload
- **Estimate:** ~100 lines
- **Files:** Existing `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/simulation/workers.py` only if a focused extension is needed, `tests/loader/test_schematisation.py`, relevant task tests
- **Description:** This is loader-arranged orchestration, not wizard content, so it is re-implemented in the existing `loader.py` rather than copied. Use the current `SchematisationUploadTask` (the current replacement for legacy `SchematisationUploadProgressWorker`) for initial revision uploads. Use legacy `save_initial_revision()` only to understand how revision 0 and its upload specification are assembled. Verify current task support first; extend the existing task narrowly only if necessary. Keep UI and Browser updates on the main thread. Independent of the wizard port in Task 4; needs only a caller to supply the schematisation/local-schematisation context.
- **Depends on:** None
- **Acceptance:** Initial upload reuses the current QgsTask lifecycle and correctly reports success, failure, and cancellation; no legacy worker/thread lifecycle is ported.
- **Evidence:** Focused tests verify revision-0 specification, task outcome handling, and Browser refresh only after success.

### From-scratch UI and local preparation

#### Task 7: Port the From scratch explanation and settings wizard to Qt 6
- **Estimate:** ~220 lines
- **Files:** Copied `rana_qgis_plugin/widgets/new_wizard_pages/{explain.py,settings.py}`, copied `rana_qgis_plugin/widgets/schematisation_new_wizard.py`, widget tests
- **Description:** Port the legacy explanation step and full settings form, including CRS, 1D/2D/0D options, timestep/numerical fields, optional raster inputs, conditional controls, and legacy-required validation. Use current Qt 6/QGIS widget patterns and keep the From scratch flow separate from Upload existing.
- **Depends on:** Task 4
- **Acceptance:** The wizard presents the explanation and full settings flow; its validation returns settings in a form suitable for schema preparation.
- **Evidence:** Focused widget tests cover required CRS/timestep, conditional flow settings, raster validation, and settings collection.

#### Task 8: Create and populate the From scratch GeoPackage
- **Estimate:** ~150 lines
- **Files:** Copied `rana_qgis_plugin/widgets/schematisation_new_wizard.py`, focused current helper module only if needed, tests under `tests/simulation/`
- **Description:** Create/upgrade a new schematisation GeoPackage from validated wizard settings, populate the required schema tables, and copy configured rasters into the local revision. Reuse current raster mapping helpers where appropriate; avoid a generalized schema framework.
- **Depends on:** Task 7
- **Acceptance:** Valid settings produce a usable populated GeoPackage and expected raster files; invalid inputs fail before upload.
- **Evidence:** Tests inspect a real/minimal GeoPackage fixture for populated settings and verify copied raster outputs.

### Route integrations

#### Task 9: Integrate Upload existing with registration and initial upload
- **Estimate:** ~90 lines
- **Files:** Existing `rana_qgis_plugin/loader.py`, copied current wizard module, relevant loader/widget tests
- **Description:** Connect Upload existing from the submenu to metadata collection, local preparation, Rana registration at the invoking folder path, and Task 6's initial-revision upload. Report API/task errors, refresh after success, and do not auto-open.
- **Depends on:** Tasks 1, 5, 6
- **Acceptance:** A valid existing file completes registration and initial upload to the selected folder; conflict/failure/cancel paths do not report success or overwrite existing data.
- **Evidence:** Loader-level tests cover success, local/remote conflict, cancellation, upload failure, and success-only Browser refresh.

#### Task 10: Integrate From scratch with registration and initial upload
- **Estimate:** ~90 lines
- **Files:** Existing `rana_qgis_plugin/loader.py`, copied current wizard module, relevant loader/widget tests
- **Description:** Connect From scratch from the submenu to the full wizard, local GeoPackage preparation, Rana registration at the invoking folder path, and Task 6's initial-revision upload. Report errors, refresh after success, and do not auto-open.
- **Depends on:** Tasks 1, 6, 7, 8
- **Acceptance:** Valid wizard settings produce a registered schematisation with an uploaded initial revision at the selected folder; failure/cancel paths do not report success or overwrite.
- **Evidence:** Loader-level tests cover the creation/upload handoff and success-only refresh.

### Cross-route verification

#### Task 11: Verify route integration and manual UI paths
- **Estimate:** ~80 lines
- **Files:** Focused tests under `tests/data_items/`, `tests/loader/`, and `tests/widgets/`; design/task notes if behavior changes
- **Description:** Verify consistent target-folder handling, error/conflict behavior, Browser refresh only after success, and no automatic open across all three routes. Run relevant unit/integration tests and provide manual UI paths. E2E tests are excluded unless separately approved.
- **Depends on:** Tasks 3, 9, 10
- **Acceptance:** All route and regression tests pass and manual paths are documented for root, nested folders, all routes, and cancellation/error states.
- **Evidence:** Relevant unit/integration suite passes; final task report names manual UI paths.

## Dependencies & Execution Order

- Task 1 is the shared UI entry point. HCC and both wizard routes depend on it
  for their menu wiring/integration.
- Tasks 2 → 3 are sequential for HCC revision import.
- Task 4 establishes copied Qt 6 wizard modules and shared metadata,
  including the migrated local name-conflict check. Tasks 5 and 7 can proceed
  in parallel after it.
- Task 6 has no dependency on Task 4: it is loader-side orchestration, not
  wizard content, and only needs a caller to supply schematisation/local
  context. It can be implemented at any point, including in parallel with
  Tasks 2–5, 7.
- Task 8 depends on the From scratch settings contract in Task 7.
- Task 9 depends on Upload existing preparation and initial-upload handling
  (Tasks 5 and 6).
- Task 10 depends on From scratch UI, schema preparation, and initial-upload
  handling (Tasks 6–8).
- Task 11 is the final cross-route verification.

### Parallel Opportunities

- Tasks 2, 4, and 6 can be developed independently of each other from the
  start; HCC work, wizard porting, and loader-side upload orchestration are
  separate concerns.
- After Task 4, Tasks 5 and 7 can be reviewed in parallel where code-file
  ownership is coordinated; both touch copied modules and should not edit the
  same file simultaneously.
- Task 3 follows Task 2; Task 8 follows Task 7; route integrations follow
  their corresponding preparation and upload tasks.

## Notes

- Preserve legacy source files under `rana_qgis_plugin/legacy/`; copy the
  schematisation wizard and page modules before adapting them.
- Migration approach differs by layer: wizard/dialog files are **migrated**
  (copy legacy file, then adapt — including validation logic such as the
  local name-conflict check that already lives in the wizard). Loader
  orchestration is **re-implemented** in the existing `loader.py`, using the
  legacy loader only as behavioral reference, because the current loader's
  architecture (QgsTask-based, no legacy signals/communication object) can't
  be copied as-is.
- Edit the existing `rana_qgis_plugin/loader.py`; do not create a parallel
  loader solely for this feature.
- Use upstream commit `5a603a5cce555e1ee17c132aab9edc6191053d16` only as the
  reference for HCC revision import behavior and path convention.
- `SchematisationUploadTask` is the current counterpart to the legacy
  `SchematisationUploadProgressWorker`; do not reintroduce the old worker.
- If registration succeeds but local preparation/upload later fails, report
  partial state safely. Do not automatically delete remote schematisations
  without an explicit API/product decision.
- Manual UI testing paths: Files root; nested folder; Import from HCC;
  Upload existing (`.gpkg` and `.sqlite`); From scratch; cancellation,
  validation errors, API conflicts, and successful Browser refresh.

## Progress

- [x] Task 1: Add the Add schematisation submenu to folder items
- [x] Task 2: Port upstream HCC revision selection behavior into current UI
- [x] Task 3: Copy the selected HCC revision and refresh the Browser
- [x] Task 4: Copy legacy wizard/page modules and port shared metadata UI to Qt 6
- [ ] Task 5: Port Upload existing input validation and local preparation
- [ ] Task 6: Reuse SchematisationUploadTask for initial revision upload
- [ ] Task 7: Port the From scratch explanation and settings wizard to Qt 6
- [ ] Task 8: Create and populate the From scratch GeoPackage
- [ ] Task 9: Integrate Upload existing with registration and initial upload
- [ ] Task 10: Integrate From scratch with registration and initial upload
- [ ] Task 11: Verify route integration and manual UI paths
