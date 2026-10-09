---
feature: feat_456_create_schema
status: planned
created: 2026-10-08
decisions:
  - 20261008-1510-schematisation-action-submenu
  - 20261008-1515-schematisation-target-folder
  - 20261008-1520-schematisation-success-followup
  - 20261008-1530-schematisation-explanation-step
  - 20261008-1540-schematisation-missing-raster-validation
  - 20261008-1550-hcc-import-specific-revision
  - 20261008-1600-existing-schematisation-file-formats
  - 20261008-1610-schematisation-name-conflicts
  - 20261008-1620-full-schematisation-settings
  - 20261008-1630-shared-schematisation-creation-flow
  - 20261008-1640-schematisation-metadata-inputs
  - 20261008-1650-port-schematisation-dialogs-qt6
  - 20261009-1200-unify-schematisation-wizard-base-and-flow
---

# Add Schematisation Design

## Overview

Port the legacy add-schematisation functionality into the current Rana QGIS
plugin as three user routes: import a selected HCC schematisation revision,
upload an existing local schematisation, and create a schematisation from
scratch. The feature uses the current plugin's Browser actions, API integration,
error reporting, and QGIS task lifecycle. Legacy dialogs and wizards are the
UI reference for the upload-existing and from-scratch routes, and will be
ported to Qt 6 rather than replaced with new dialog designs.

## User Scenarios & Testing

### User Story 1 - Import an HCC revision (Priority: P1)

As a user, I want to select an HCC schematisation and one of its revisions to
copy into a Rana project folder, so that I can work with a specific upstream
revision in Rana.

**Why this priority**: This is one of the three requested add-schematisation
routes and is a distinct server-side copy workflow.

**Independent Test**: Invoke Add schematisation on the Files root or a folder,
select Import from HCC, choose a schematisation and revision, and verify that
the selected revision is copied to the target path and appears after Browser
refresh.

**Acceptance Scenarios**:

1. **Given** the HCC selection dialog is open, **when** schematisations are
   fetched, **then** a searchable schematisation list is shown.
2. **Given** a schematisation is selected, **when** its revisions are fetched,
   **then** revisions are shown newest first and the newest revision is
   selected by default when available.
3. **Given** both a schematisation and revision are selected, **when** the user
   confirms, **then** the selected `schematisation_id` and `revision_id` are
   sent to the Rana copy API.
4. **Given** the action was invoked at a folder path, **when** the copy is
   requested, **then** the destination is that folder plus the upstream
   revision-number suffix path convention.
5. **Given** the copy succeeds, **when** completion is handled, **then** the
   Browser refreshes and the schematisation is not automatically opened.
6. **Given** fetching or copy fails, **when** the operation completes, **then**
   an actionable error is shown and the Browser is not falsely refreshed as if
   the copy succeeded.

### User Story 2 - Upload an existing schematisation (Priority: P1)

As a user, I want to select an existing GeoPackage or SQLite schematisation,
provide its Rana metadata, and upload it into the folder where I invoked the
action.

**Why this priority**: This supports users who already have model data and is
one of the three requested routes.

**Independent Test**: Invoke Upload existing on a folder, select a valid
`.gpkg` or `.sqlite` input, complete the ported wizard, and verify that the
schematisation is registered and its initial revision uploads through the
current task flow.

**Acceptance Scenarios**:

1. **Given** Upload existing is selected, **when** the input file picker opens,
   **then** `.gpkg` and `.sqlite` inputs are available.
2. **Given** a supported file is selected, **when** the user completes the
   ported Qt 6 dialog, **then** required name, optional description, and
   organisation/owner metadata are collected (with the organisation selector
   hidden when there is only one option).
3. **Given** a SQLite source requires normalization, **when** preparation
   succeeds, **then** the local schematisation uses the expected GeoPackage
   representation.
4. **Given** the source schema is invalid or a referenced raster is missing,
   **when** validation runs, **then** the flow stops before upload and explains
   the problem.
5. **Given** the destination name already exists locally, **when** the user
   proceeds, **then** the flow rejects the duplicate without overwriting.
6. **Given** local preparation succeeds, **when** the initial revision uploads,
   **then** long-running work uses a `QgsTask` and successful completion
   refreshes the Browser without automatically opening the schematisation.
7. **Given** Rana rejects a duplicate remote path or the upload fails, **when**
   completion is reported, **then** the user receives an error and no overwrite
   is attempted.

### User Story 3 - Create a schematisation from scratch (Priority: P1)

As a user, I want to configure and create a new schematisation from scratch,
so that the resulting initial revision has the model settings and schema I
need.

**Why this priority**: This completes the requested creation routes and retains
the established legacy model-configuration workflow.

**Independent Test**: Invoke From scratch on a folder, complete the ported Qt 6
wizard with valid model settings, and verify that the new schema is populated,
its initial revision uploads, and the Browser refreshes.

**Acceptance Scenarios**:

1. **Given** From scratch is selected, **when** its wizard opens, **then** the
   ported legacy name/explanation/settings flow is presented.
2. **Given** the wizard is completed, **when** input is validated, **then** the
   required projected CRS, enabled flow settings, timestep/numerical values,
   and raster inputs are checked according to their applicable rules.
3. **Given** valid settings, **when** local creation runs, **then** a new
   schematisation GeoPackage is initialized and populated from those settings.
4. **Given** the destination name already exists locally, **when** the user
   proceeds, **then** the flow rejects the duplicate without overwriting.
5. **Given** local preparation succeeds, **when** the initial revision uploads,
   **then** long-running work uses a `QgsTask` and success refreshes the Browser
   without automatically opening the schematisation.
6. **Given** the Rana API rejects the path or upload fails, **when** the error is
   handled, **then** the user receives an error and no overwrite is attempted.

### User Story 4 - Start any route from the Browser folder context (Priority: P1)

As a user, I want one Add schematisation context-menu entry with a submenu on
the Files root and every folder, so that I can choose a route at the location
where I want its result stored.

**Independent Test**: Open the context menu on the Files root and on nested
folders, verify the submenu has all three routes, and verify each route targets
the invoking folder (the Files root targets the project root).

**Acceptance Scenarios**:

1. **Given** the Files root or any folder item, **when** its context menu is
   opened, **then** it contains one Add schematisation entry with Import from
   HCC, Upload existing, and From scratch submenu choices.
2. **Given** a route is selected from a folder, **when** it creates or copies a
   Rana schematisation, **then** it uses that folder as destination without a
   second destination picker.
3. **Given** a route is selected from the Files root, **when** it creates or
   copies a Rana schematisation, **then** it targets the project root.

### Edge Cases

- HCC schematisation has no revisions: confirmation remains disabled and no
  copy request is issued.
- HCC list or revision fetch fails: show an error and allow retry/cancel.
- Copy or create API reports a path conflict: show the API error; do not
  overwrite or silently retry.
- Local schematisation name already exists: reject before registering a new
  remote schematisation.
- Existing GeoPackage schema is invalid or a referenced raster is absent: stop
  before uploading and identify the validation issue.
- Raster paths selected in the From scratch wizard are invalid or unreadable:
  report validation errors before registration/upload where possible.
- User cancels a file picker or wizard: do not create remote or local
  schematisation state.
- Network, task cancellation, or upload failure occurs after remote registration:
  report the failure and avoid claiming success; cleanup/recovery behavior for
  partially created remote/local state must be handled safely.
- Only one owner organisation is available: use it without showing a
  redundant selector.

## Design Decisions

### Context menu and target folder

Use one Add schematisation action with a submenu for the three routes. Make it
available on the Files root and every folder, following the existing folder
action pattern for upload files and create directory. Pass the invoking
`folder_path` to the selected route. The Files root's empty path targets the
project root; do not ask for a second destination.

### Port existing dialogs to Qt 6

Port the legacy Upload existing and From scratch dialogs/wizards to Qt 6 and
the current plugin architecture. Preserve their distinct flow/page structures
and useful validation. Replace legacy browser/loader wiring, authentication
helpers, and threading/lifecycle patterns with current-plugin equivalents.

Keep the From scratch explanation step. The two flows remain separate, with
route-specific page setup and preparation logic. A focused
`SchematisationWizardBase` owns only their shared wizard interface and common
QWizard setup/lifecycle; it is not a mode-driven or generalized wizard
framework. Loader shares authentication, organisation lookup, wizard execution,
and initial-revision upload orchestration through one helper.

### Post-implementation consolidation

The two Loader entry methods and wizard classes now share a common calling
contract. Use a private Loader orchestration helper with route-specific wizard
factories. `SchematisationWizardBase` owns common constructor state and output
attributes (`new_schematisation`, `new_local_schematisation`, `raster_paths`),
the shared name page and button wiring, and close lifecycle. Each subclass
provides its own title and settings key and adds its own route-specific pages.
Keep validation and local preparation in their respective wizard subclasses;
the base must not turn the two flows into a mode-driven wizard.

The base also owns the common build-error handling helper used by each
subclass's build method. That helper catches the existing API/Rana exceptions
and general exceptions, clears all three output attributes on failure, and
reports the error using the existing communication methods. Route-specific
early aborts (such as invalid existing-file preparation returning `None`)
remain in the Upload existing flow and should not be converted into exceptions
just to fit the shared helper.

Local name-conflict validation and shared Rana/local schematisation setup are
also methods on `SchematisationWizardBase`, since both wizard routes use them
and their dependencies (working directory, communication, API client, project
ID, and destination path) are already base-class state. The setup method does
not accept an owner argument: Rana registration currently uses path and
description, while the selected owner is part of the wizard metadata/UI rather
than this create call.

Give each wizard a distinct QSettings key for remembered window size. Persist
the size consistently via the shared `done()` lifecycle when a wizard closes.
Keep upload-specific preparation
and copy helpers with the Upload existing flow. Put
`get_paths_from_geopackage`, which is called by both wizard flows, on the base
class as a static method so neither subclass needs to depend on the other's
class. No helpers need to become module-level functions for this consolidation.

This consolidation supersedes decisions `20260511-1413-split-schematisation-wizard`
and `20261008-1630-shared-schematisation-creation-flow`; see
`20261009-1200-unify-schematisation-wizard-base-and-flow`.

### Import a specific HCC revision

Follow upstream commit
`5a603a5cce555e1ee17c132aab9edc6191053d16`. Present a searchable
schematisation selection and a revision selection for the chosen
schematisation. Sort revisions newest first and preselect the newest when
available. The copy request includes both schematisation and revision IDs. Use
the upstream revision-number suffix convention in the destination path.

### Upload/create metadata and conflicts

For Upload existing and From scratch, collect a required name, optional
description, and owning organisation. Hide the organisation selector if there
is only one available choice. Retain legacy local duplicate-name rejection,
do not add overwrite semantics, and report remote path-conflict errors returned
by Rana.

### Upload existing inputs

Accept both `.gpkg` and `.sqlite` files. Validate the schema and normalize
SQLite input to the expected GeoPackage representation as needed. Extract
raster references and block the flow if any referenced raster is missing,
matching legacy behavior.

### From-scratch inputs

Retain the full legacy configuration scope and schema-population behavior:
projected CRS; 1D, 2D, and 0D options; simulation timestep and numerical
settings; optional raster inputs; their conditional validation; and creation
and population of the new GeoPackage. Use the legacy flow as behavioral
reference while porting to current Qt 6 and QGIS patterns.

### Completion behavior

On successful completion of any route, refresh the Browser so the new
schematisation appears. Do not automatically open/load it in the
Schematisation Editor; opening remains a separate user action. No process-link
popup or auto-selection is included.

### Background work and errors

Use current API wrappers and error types where available. Long-running
conversion, preparation, and upload operations must not freeze QGIS. Use the
current `QgsTask` lifecycle for upload work; do not port legacy QThread worker
lifecycle patterns. Dialogs and QGIS Browser updates remain on the main thread.

The current `SchematisationUploadTask` is the starting point for initial
revision upload. During implementation, verify whether it supports an initial
revision directly; if not, make a focused extension that reuses its task
lifecycle and upload behavior.

## Components

### Browser actions

- Extend `data_items/file_actions.py` with the Add schematisation parent action
  and route submenu labels/tooltips/icons as needed.
- Extend `data_items/folder_item.py` to expose and route the submenu on the
  Files root and all folder items, passing project and target folder context.
- Reuse current item refresh patterns to repopulate the Browser after success.

### HCC import UI and flow

- Port/adapt the schematisation-and-revision selection dialog to current Qt 6
  UI conventions.
- Reuse `ThreediCalls.fetch_schematisations_with_count()` and
  `fetch_schematisation_revisions()` for HCC data where compatible.
- Reuse the current Rana copy wrapper, updating it only as needed to pass the
  selected revision ID per upstream behavior.
- Surface fetch/copy errors through current communication/error handling.

### Upload existing and From scratch UI

- Port legacy wizard/page content to Qt 6 using QGIS Qt imports.
- Keep separate Upload existing and From scratch flow classes/pages, with
  narrowly shared creation/setup helper logic.
- Reuse `SchematisationApiMapper` for raster-reference mapping where
  applicable.
- Reuse current metadata, authentication, and API wrappers instead of legacy
  communication or loader signals.

### Local preparation and initial revision upload

- Validate/normalize existing input and prepare local schematisation working
  directories.
- Create and populate a new schema for From scratch.
- Integrate initial revision upload with the current
  `SchematisationUploadTask`/`Loader` lifecycle.
- Report task progress, cancellation, and failure using current patterns;
  refresh the Browser only after successful completion.

## Data Model

The three routes share these contextual values:

```python
project_id: str
target_folder_path: str  # empty for project root
```

The user inputs for Upload existing and From scratch are:

```python
name: str                # required
description: str | None
owner_organisation_id: str
```

HCC import additionally selects:

```python
schematisation_id: str
revision_id: str
revision_number: int      # used for the destination path suffix
```

Existing-file input is a local `.gpkg` or `.sqlite` path. From-scratch input
is the validated model-configuration/settings structure produced by its
wizard. Exact request/result data classes are left to implementation design;
avoid adding wrappers or abstractions until the current loader/task interfaces
are inspected and the required values are clear.

## API / Interface

- **Context action:** Add schematisation submenu action routed from each
  `RanaFolderDataItem` with its project and `folder_path`.
- **HCC import:** Fetch/search schematisations; fetch revisions for the
  selected schematisation; copy with project ID, source schematisation ID,
  selected revision ID, and destination path containing the revision-number
  suffix.
- **Create Rana schematisation:** For Upload existing and From scratch, call
  the current Rana create endpoint with the target path and optional
  description, after local-name validation.
- **Prepare local content:** Upload existing validates and copies/normalizes
  source files and referenced rasters. From scratch creates/upgrades and
  populates a GeoPackage and copies configured rasters.
- **Initial revision upload:** Use the current task-based schematisation
  upload flow, with a focused extension if the current task does not support
  initial revisions.
- **Completion:** On success, refresh the invoking folder/root. Do not
  auto-open the result.

## Testing Strategy

Unit/integration tests should cover real behavior and API/task boundaries where
available:

- Parent context action and three submenu routes appear on Files root and
  nested folders, with the correct target path supplied.
- HCC import revision ordering/default selection, missing revisions, copy
  payload including `revision_id`, destination suffix, and API error handling.
- Upload existing accepts both supported file extensions, validates schema,
  normalizes SQLite as required, extracts referenced rasters, and blocks on
  missing rasters.
- From-scratch settings validation and conversion into populated schema
  settings, including conditional CRS/flow/timestep/raster constraints.
- Local duplicate rejection and Rana remote path conflict reporting without
  overwrite.
- Shared initial-revision upload success, failure, and cancellation through
  `QgsTask` behavior.
- Browser refresh after success and no automatic opening for all three routes.
- Qt 6 compatibility of all ported dialogs/wizard pages and QGIS-only Qt
  imports.

E2E tests are not included without explicit approval. Manual testing is
required for the context menu on the Files root and nested folders, each of the
three routes, cancellation/error states, and successful Browser refresh.

## Scope Boundaries

Included:

- Add schematisation submenu on the Files root and every folder.
- HCC schematisation-and-revision import using upstream behavior.
- Upload existing from `.gpkg` and `.sqlite`, including schema/raster
  validation and normalization.
- From-scratch wizard with full legacy configuration and schema population.
- Port of the existing Upload existing and From scratch dialogs/wizards to
  Qt 6/current-plugin architecture.
- Shared schematisation setup and initial-revision upload behavior where
  supported by current task architecture.
- Browser refresh after successful completion without automatic opening.
- Unit/integration tests and manual-testing guidance.

Not included:

- Automatically opening/loading a newly imported or uploaded schematisation.
- Overwriting an existing local or remote schematisation.
- New process-link popup behavior or automatic Browser selection.
- E2E tests without explicit approval.
- Reworking unrelated legacy plugin code.

## Open Questions / Implementation Checks

- Verify whether `SchematisationUploadTask` supports initial revision upload
  as-is; otherwise design a narrow extension that follows its lifecycle.
- Confirm the exact Rana destination path joining and revision suffix details
  against upstream commit `5a603a5cce555e1ee17c132aab9edc6191053d16` during
  implementation, including path separator/encoding expectations.
- Define safe cleanup/recovery if the Rana schematisation is registered but
  local preparation or initial revision upload subsequently fails. Do not
  silently delete remote state without an explicit API/product decision.
