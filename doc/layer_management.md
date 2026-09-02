# Layer management

This document describes the module-level layer-opening functions used by the
Rana Browser. Download and styling mechanics are documented separately in
[`download_workers.md`](download_workers.md) and
[`styling_workers.md`](styling_workers.md).

## Layer-opening flow

After a `DownloadTask` completes, the Browser calls the appropriate opening
function for the downloaded resource:

- `open_rana_vector_layers()` opens all layers in a vector file;
- `open_rana_vector_layer()` opens one named vector layer; and
- `open_rana_raster()` opens a raster file.

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

That group receives a **Save revision** action. The save flow checks for unsaved
layer edits, confirms the upload through the upload wizard, and runs the upload
through `SchematisationUploadTask`. The action is disabled while that task is
active and the revision number is updated only after success. QGIS 4.2 Python
bindings do not currently provide a reliable layer-level edit/commit guard, so
users should not edit schematisation layers during upload.

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
- Rana file path;
- file descriptor ID; and
- vector layer ID, where applicable.

The reference helpers provide set, get, clear, and linked-state operations.
Custom properties persist with the QGIS project, so no separate reference
registry is required.

## Dirty-state tracking

When a linked layer is added:

- committed vector edits set `rana/data_dirty`; and
- `styleChanged` on any linked layer sets `rana/style_dirty`.

The flags are cleared only after the corresponding synchronization succeeds.
The layer-tree menu uses them to enable or disable the relevant save action.
There is currently no separate layer-tree badge or name decoration.

## Layer-tree synchronization menu

The layer-tree menu provider adds actions for Rana-linked groups:

- **Save style to Rana** uploads style files for the linked layer or file;
- **Save styles to Rana** is used when a group contains multiple files; and
- **Save data to Rana** is available at file level only.

Data upload replaces the complete Rana file, so it is not offered for an
individual layer inside a multi-layer vector file. A central lock registry
prevents concurrent synchronization of the same Rana file. The loader also
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
