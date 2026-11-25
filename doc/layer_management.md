# Layer management

This document describes the module-level layer-opening functions used by the
Rana Browser. Download and styling mechanics are documented separately in
[`download_workers.md`](download_workers.md) and
[`styling_workers.md`](styling_workers.md). Unsynced-change tracking is
documented in [`dirty_tracking.md`](dirty_tracking.md).

## Layer-opening flow

After a `DownloadTask` completes, the Browser calls the appropriate opening
function for the downloaded resource:

- `open_rana_vector_layers()` opens all layers in a vector file;
- `open_rana_vector_layer()` opens one named vector layer; and
- `open_rana_raster()` opens a raster file;
- `open_rana_wms()` adds the WMS layers of a descriptor (its `wms` link) to the Rana layer tree, skipping layers that are invalid or lack code, name or label; and
- `open_rana_schematisation()` loads a downloaded schematisation revision (or the WIP revision) into the schematisation editor and tags its group (see below).
- `open_scenario_results_in_results_analysis()` opens a scenario using the Results Analysis plugin. See [`scenario_results.md`](scenario_results.md) for all details.

WMS opening is module-level, see
[`20260921-1800-wms-module-level-layer-opening.md`](../.minispec/knowledge/decisions/20260921-1800-wms-module-level-layer-opening.md).

The functions receive the local file path, Rana reference, and display-path
segments. They create QGIS layers, add them to the current project, and attach
dirty-state tracking to each linked layer.

## Schematisation opening and saving

Schematisations are opened from the Browser through double-click, context-menu,
multi-select, and folder-selection flows. The loader resolves the local working
directory before starting a `DownloadTask`. If a local WIP conflicts with the
requested revision, the user can replace it, store the download as a separate
revision, or cancel.

After loading, the top-level group is tagged with:

- `rana/schematisation_id`;
- `rana/revision_number`; and
- `rana/schematisation_db_filepath`.

That group receives a **Save revision** action in the layer panel. The action
handles unsaved edits in the open schematisation layers and uploads the local
working-in-progress (WIP) revision through the local WIP upload flow, using
`SchematisationUploadTask`. The action is disabled while an upload is active.
After a successful upload, the layer-group revision metadata
(`rana/revision_number` and related group tags) is not rewritten; the group
keeps the metadata it was loaded with.

A schematisation's local revision can also be uploaded from the Browser without
opening it as a WIP layer group. The file-browser **Save local revision** action
is that non-open-WIP entry point.

Both revision-upload entry points use the same message-bar lifecycle. A busy
bar shows while layer changes and revision metadata are prepared, and is
removed before the upload wizard opens. After the wizard is accepted, one
progress item is updated in place for the upload; progress ticks do not create
additional message-bar items. The item is removed on success, cancellation,
or failure, followed by a single final message. A model-checker failure makes
clear that the revision was uploaded but no model was created. When model
creation starts, the user can follow the job in the Processes panel.


## Layer-tree groups

The group builder performs a find-or-create walk for the supplied path:

```text
Project
└── files
    └── folder
        └── file.gpkg
            └── layer name
```

Group identity uses Rana reference metadata (`project_id` and path segment),
not display names alone. Reopening a file therefore reuses matching groups
without creating duplicate hierarchies, while same-named paths from different
projects remain distinct.

Vector files use the OGR provider and a `path|layername=...` data-source URI.
Raster files create one `QgsRasterLayer`. If downloaded QML styling is
available, it is applied while the layer is created.

## Rana references

Each opened layer stores its Rana reference as QGIS custom properties under the
`rana/` namespace:

- project ID;
- project name (`rana/project_name`, optional: absent on layers linked
  before it was stored);
- Rana file path;
- file descriptor ID; and
- vector layer ID, where applicable.

The reference helpers provide set, get, clear, and linked-state operations.
Custom properties persist with the QGIS project, so no separate reference
registry is required.

## Dirty-state tracking

Each linked layer tracks whether its data and style have unsynced local
changes, using different detection strategies for vector edits, raster file
changes, and style changes. This state gates the layer-tree save actions,
drives a layer-tree warning badge, and backs a prompt that offers to sync
before a project or layer is closed. See
[`dirty_tracking.md`](dirty_tracking.md) for the full state model and flow.

## Layer-tree synchronization menu

The layer-tree menu provider adds actions for Rana-linked groups:

- **Sync style to Rana** uploads style files for the linked layer or file;
- **Sync styles to Rana** is used when a group contains multiple files; and
- **Sync data to Rana** is available at file level only.

Choosing a sync action opens a confirmation dialog listing the affected
files and layers; the user can deselect individual files, and only the checked
files are synchronized. See [`dirty_tracking.md`](dirty_tracking.md).

Data upload replaces the complete Rana file, so it is not offered for an
individual layer inside a multi-layer vector file. A central lock registry
prevents concurrent uploads and downloads of the same Rana file: opening a
file that is being uploaded is refused, and batch opens skip it. While a file
uploads, its vector layers are read-only, and a file with unsaved edits is not
uploaded. See [Sync locking](sync_locking.md). The loader also
checks that the remote target still exists immediately before saving.

## Local reference updates

The loader emits rename and delete signals after successful Browser actions.
The local-linking listener handles them as follows:

- renaming a file or folder updates the stored path prefix on affected layers;
- deleting a file or folder clears the affected Rana references; and
- the QGIS layers and their display names remain unchanged.

Remote changes cannot be observed proactively. A definitive not-found result
from the pre-save check clears the link and disables synchronization. A
transient verification error preserves the link and allows a later retry.
