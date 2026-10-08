---
feature: file-listing
 status: complete
created: 2026-08-05
---

# File Listing Design

## Overview

Adds lazy file tree browsing under each project in the QGIS Browser panel using native `QgsDataItem` subclasses. A "Files" container node appears under each project; expanding it fetches the root-level files and folders from the Rana API. Folders load their contents on demand. Vector files expand to show contained layers (fetched from the file descriptor). All items follow the existing `RanaRootDataItem` patterns for error handling and refresh.

## User Stories

- As a user, I want to see a "Files" node under each Rana project so I know where project files live.
- As a user, I want to expand folders and see their contents only when I open them, so the initial UI is fast.
- As a user, I want to expand a vector file to see its contained layers, then open a layer in QGIS.
- As a user, I want to right-click nodes to access relevant actions (refresh, upload, create folder, open in QGIS, open in browser, version history).
- As a user, I want network or fetch errors to surface as error items in the tree rather than silent failures.

## Tree Hierarchy

```
Rana (RanaRootDataItem)
  └── Project A (RanaProjectDataItem)
       └── Files (RanaFilesDataItem)
            ├── 📁 folder/ (RanaFolderDataItem)
            │    ├── 📄 roads.gpkg (RanaFileDataItem — vector, expandable)
            │    │    ├── 🔷 roads (RanaLayerDataItem — LineString)
            │    │    └── 🔶 buildings (RanaLayerDataItem — Polygon)
            │    └── 📄 elevation.tif (RanaFileDataItem — raster, leaf)
            └── 📄 standalone.csv (RanaFileDataItem — other, leaf)
```

## Components

Five new files under `data_items/`:

### `data_items/files_item.py` — `RanaFilesDataItem`
Container node "Files" under each `RanaProjectDataItem`. Calls the file listing API for the root path on expand. Provides a Refresh action and a folder-style context menu targeting the root path (no Delete option).

### `data_items/folder_item.py` — `RanaFolderDataItem`
Represents a directory. `createChildren()` fetches one level of contents for its path. Provides a folder context menu including Delete.

### `data_items/file_item.py` — `RanaFileDataItem`
Represents a single file. Vector files are expandable: `createChildren()` fetches the file descriptor and returns `RanaLayerDataItem` children. All other types are leaves. Context menu is data-type-aware.

### `data_items/layer_item.py` — `RanaLayerDataItem`
Represents a single layer inside a vector file. Always a leaf. Context menu: Open in QGIS only.

### `data_items/file_actions.py` — action helper module
Defines a `FileAction` enum (subset of legacy), icons, tooltips, and two functions:
- `get_file_actions(data_type: str) -> list[FileAction]`
- `get_folder_actions(is_root: bool = False) -> list[FileAction]`

Copied from `legacy/widgets/utils_file_action.py` where reusable; drops all legacy dependencies (`auth_3di`, `FileActionSignals`, descriptor API calls).

## Data Model

Each item carries only what it needs to display and load children:

| Item | Key fields |
|---|---|
| `RanaFilesDataItem` | `project_id`, `error_signals` |
| `RanaFolderDataItem` | `project_id`, `folder_path`, `name`, `error_signals` |
| `RanaFileDataItem` | `project_id`, `file_path`, `file_descriptor_id`, `name`, `data_type`, `error_signals` |
| `RanaLayerDataItem` | `file_descriptor_id`, `layer_id`, `name`, `geometry_type`, `error_signals` |

## API / Interface

- File listing: `GET /tenants/{tenant_id}/projects/{project_id}/files/ls?path=<path>` with cursor-based pagination. Raises `FetchError` on failure (does not swallow errors).
- File descriptor (for vector expansion and scenario right-click): `GET /tenants/{tenant_id}/file-descriptors/{file_descriptor_id}`. Fetched lazily.
- `error_signals` is created at `RanaProjectDataItem` and passed down through the entire hierarchy.

## Context Menus

All actions are present but **unconnected** in this version.

**`RanaFilesDataItem` (root):**
- Refresh
- Create directory
- Upload file(s)
- Version history
- Open in web

**`RanaFolderDataItem`:**
- Refresh
- Create directory
- Upload file(s)
- Version history
- Open in web
- *(separator)*
- Delete

**`RanaFileDataItem` by `data_type`:**

| Action | vector | raster | threedi_schematisation | scenario | other |
|---|---|---|---|---|---|
| Open in QGIS | ✅ | ✅ | ✅ | — | — |
| Open WMS | — | — | — | ✅* | — |
| Download results | — | — | — | ✅* | — |
| Open in browser | ✅ | ✅ | ✅ | — | ✅ |
| Rename | ✅ | ✅ | ✅ | ✅ | ✅ |
| *(separator)* | | | | | |
| Delete | ✅ | ✅ | ✅ | ✅ | ✅ |

*Scenario: Open WMS and Download results require fetching the file descriptor on right-click (lazy). Optimize to eager if latency is noticeable.

**`RanaLayerDataItem`:**
- Open in QGIS

## Icon Strategy

- **Folders:** `dir_icon` from `icons.py`
- **Files:** `get_icon_from_theme(get_file_icon_name(data_type))` from `utils/generic.py`
- **Layers:** QGIS theme icons mapped from `layer.type`:

| `layer.type` | Icon |
|---|---|
| `Point` | `mIconPointLayer.svg` |
| `LineString` | `mIconLineLayer.svg` |
| `Polygon` | `mIconPolygonLayer.svg` |
| `MultiPoint` | `mIconPointLayer.svg` |
| `MultiLineString` | `mIconLineLayer.svg` |
| `MultiPolygon` | `mIconPolygonLayer.svg` |
| `GeometryCollection` | `mIconGeometryCollectionLayer.svg` |
| `raster` | `mIconRaster.svg` |
| `null` / unknown | generic file icon |

## Error Handling

All `createChildren()` implementations follow the same pattern as `RanaRootDataItem` (`rana_item.py:92-99`):

```python
try:
    # ... API call ...
except NetworkUnavailableError:
    self.error_signals.connection_lost.emit()
    return [QgsErrorItem(self, "No connection to Rana", self.path())]
except FetchError as e:
    self.error_signals.fetch_error_occurred.emit(str(e))
    return [QgsErrorItem(self, "Failed to load files", self.path())]
```

## Pagination

Cursor-based pagination identical to `get_tenant_project_files()` in `utils/api.py:204-222`, but raising `FetchError` rather than swallowing it.

## Out of Scope

- Connecting any context menu action handlers
- Upload, download, rename, delete implementations
- Pre-loading next level proactively (future optimization if lazy is too slow)

## Manual Testing Paths

- Expand a Rana project → "Files" node appears
- Expand "Files" → root-level folders and files listed
- Expand a folder → children load on demand
- Expand a vector file → layer children appear with correct geometry-type icons
- Right-click each item type → correct menu entries appear
- Simulate network failure → `QgsErrorItem` shown, error signals emitted
