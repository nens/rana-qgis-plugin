---
feature: feat_452_open_schema
status: complete
created: 2026-08-31
decisions:
  - 20260831-0001-schematisation-open-revision
  - 20260831-0002-schematisation-save-action
  - 20260831-0003-schematisation-upload-task
---

# Open Schematisation and Save Revision Design

## Overview

Extend the Rana browser integration so `threedi_schematisation` items can be
opened through the existing context-menu, double-click, multi-select, and
folder-select flows. The latest revision is downloaded using the existing
schematisation downloader and loaded with `LayerManager.add_from_schematisation`.
The resulting layer group exposes a Save revision action that uploads changes
without blocking QGIS.

## User Stories

- As a QGIS user, I want to open a schematisation from Rana so that I can edit
  it in the 3Di schematisation editor.
- As a QGIS user, I want selecting several items or a folder containing a
  schematisation to open it together with the other selected resources.
- As a QGIS user, I want to save a loaded schematisation as a new revision
  from its layer-group context menu.

## Components

**Legacy import policy:** none of the new code introduced by this feature
imports from `rana_qgis_plugin.legacy`. As preparatory work, the entire
`legacy/simulation/` package was moved wholesale to `rana_qgis_plugin/simulation/`
(preserving its internal structure, merged with the pre-existing
`simulation/threedi_calls.py`) rather than cherry-picking individual pieces,
since most of that code is expected to be reused by later simulation-related
features too. See `tasks.md`'s "Legacy Move" section for what moved and what
was updated.

### Browser open flow

Extend the existing `RanaFileDataItem` and `RanaDataItemGuiProvider` filters to
accept `threedi_schematisation`. Add a schematisation-specific open request and
resolve its schematisation metadata, latest revision, local working directory,
and WIP replacement choice before constructing the existing
`SchematisationRevisionDownloader` and download context.

Reuse the existing `DownloadTask` signal flow and error reporting. On
completion, call `LayerManager.add_from_schematisation` with the downloaded
local schematisation and revision information.

### Layer-group metadata and save action

When loading the schematisation, identify the created top-level layer group and
store its identity as custom properties, including schematisation ID and
revision number. Extend `LayerTreeMenuProvider` to recognize these groups and
always offer **Save revision**. The save flow determines whether there are
changes and handles a no-op without requiring separate edit-state tracking.

### Upload task

Port the behavior of `legacy/loader.py::Loader.save_revision` into a modern
`QgsTask`-based upload worker. Keep revision/WIP selection, validation,
confirmation, upload progress, completion, cancellation, and error feedback,
but avoid manual thread waiting and unsafe cross-thread UI mutation. Dialogs
and QGIS UI updates remain on the main thread; network and file work runs in
the task.

## Data Model

- Rana file items continue to use `data_type=threedi_schematisation` and
  `descriptor_id`.
- `get_threedi_schematisation(descriptor_id)` supplies schematisation and
  latest-revision metadata.
- `LocalSchematisation` and `LocalRevision` from `threedi_mi_utils` remain the
  on-disk working representation, using the existing `utils/local_paths.py`
  directory resolution.
- Loaded groups store Rana custom properties such as
  `rana/schematisation_id` and `rana/revision_number`, alongside existing
  project/path properties.

## API/Interface

- Add `OpenSchematisationRequest`, parallel to `OpenFileRequest`.
- Extend `Loader.open_items()` to resolve and download schematisations while
  de-duplicating downloads and reusing `DownloadTask` callbacks.
- Invoke `LayerManager.add_from_schematisation(project_name,
  local_schematisation, revision_number, wip_replace_requested,
  geopackage_filepath=...)` after download.
- Add a layer-tree save action that starts the upload `QgsTask` using group
  metadata.

## Error Handling

Use existing message-bar feedback for URL resolution, download, cancellation,
and task failures. Report invalid metadata, unavailable local revisions, upload
conflicts, and failed saves without leaving a partially registered group.

## Scope Boundaries

This feature does not add edit-state tracking, browser indicators for unsaved
changes, multi-schematisation batch saving, or new WIP conflict UX beyond the
legacy flow required to choose replacement versus a new WIP. It also does not
port "make 3Di model on upload" (and its model-deletion dialog); choosing that
option in the upload wizard shows a "not yet supported" message instead.

## Manual Testing Paths

- Browser context menu and double-click on a schematisation.
- Multi-select a schematisation with raster/vector files and open them.
- Select a folder containing a schematisation and open it.
- Confirm the schematisation group has **Save revision**, including when there
  are no edits, and verify successful and failed upload feedback.
- Confirm opening and saving leave QGIS responsive during network operations.

## Open Questions

- Exact UI wording and placement of the WIP replacement/new-WIP prompt should
  follow the existing legacy behavior unless implementation reveals a current
  dialog component that can be reused.
- The precise upload task result payload and progress granularity can be
  finalized while porting the legacy upload worker.
