---
feature: file-listing
 status: complete
created: 2026-08-05
chunk_size: adaptive
total_tasks: 6
estimated_lines: 305
---

# File Listing Tasks

## Overview

Implements lazy file tree browsing under each project in the QGIS Browser panel using native `QgsDataItem` subclasses. Tasks are ordered so each one produces visible progress in the browser. Context menus are added in a final pass once the tree structure is complete.

## Task List

### Foundation

#### Task 1: Update API helper — paginated file listing
- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/utils/api.py`, `tests/test_api.py`
- **Description:** Modify `get_tenant_project_files()` in `utils/api.py` to support an optional file `path`, retain the endpoint's cursor-based pagination loop (`response["next"]`), and raise `FetchError` on failure instead of swallowing errors. Do not replace this with `paginated_fetch()`, which uses offset-based pagination. Remove the legacy `UICommunication` error-reporting behavior; callers are responsible for presenting errors.
- **Depends on:** None
- **Acceptance:** Function returns all items across pages; raises `FetchError` on API failure
- **Evidence:** Unit tests cover pagination loop, empty result, and error raise

### Visual Progress — Tree Structure

#### Task 2: `RanaFilesDataItem` + wire into `RanaProjectDataItem`
- **Estimate:** ~70 lines
- **Files:** `rana_qgis_plugin/data_items/files_item.py` (new), `rana_qgis_plugin/data_items/project_item.py` (modify), `rana_qgis_plugin/data_items/rana_item.py` (modify)
- **Description:** Create `RanaFilesDataItem` — a container node labelled "Files" that appears under each project. `createChildren()` calls `get_project_files()` for the root path, returns `RanaFolderDataItem` and `RanaFileDataItem` stubs (plain `QgsDataItem` placeholders until Tasks 3–4 exist), sorts folders before files, and follows the error handling pattern from `rana_item.py:92-99`. Provides a Refresh action only (no other context menu yet). Modify `RanaProjectDataItem` to accept `error_signals`, change its item type to `Collection`, and remove `setState(Populated)` so QGIS calls `createChildren()`. Modify `RanaRootDataItem` to pass `error_signals` when constructing `RanaProjectDataItem`.
- **Depends on:** Task 1
- **Acceptance:** "Files" node visible under each project in QGIS Browser; root-level folders and files listed with icons; network error shows `QgsErrorItem`
- **Evidence:** Manual test: expand a project → "Files" node appears → expand "Files" → contents listed

#### Task 3: `RanaFolderDataItem`
- **Estimate:** ~45 lines
- **Files:** `rana_qgis_plugin/data_items/folder_item.py` (new)
- **Description:** Create `RanaFolderDataItem`. `createChildren()` fetches one level of contents for its path using `get_project_files(project_id, path=self.folder_path)`, returning `RanaFolderDataItem` and `RanaFileDataItem` children (file items still plain placeholders until Task 4). Folder icon from `dir_icon`. Error handling follows same pattern. No context menu yet.
- **Depends on:** Task 2
- **Acceptance:** Expanding a folder shows its immediate children lazily
- **Evidence:** Manual test: expand a folder → children populate on demand

#### Task 4: `RanaFileDataItem`
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/data_items/file_item.py` (new)
- **Description:** Create `RanaFileDataItem`. Non-vector files are leaves (`setState(Populated)`). Vector files are expandable but `createChildren()` returns `[]` for now (layers wired in Task 5). File icon via `get_icon_from_theme(get_file_icon_name(data_type))` from `utils/generic.py`. No context menu yet. Update `RanaFilesDataItem` and `RanaFolderDataItem` to return real `RanaFileDataItem` instances instead of placeholders.
- **Depends on:** Task 3
- **Acceptance:** Files appear with correct data-type icons; raster/other/etc. are non-expandable leaves; vector files show expand arrow
- **Evidence:** Manual test: files visible with correct icons; non-vector files have no expand arrow

#### Task 5: `RanaLayerDataItem`
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/data_items/layer_item.py` (new), `rana_qgis_plugin/data_items/file_item.py` (modify: implement `createChildren()`)
- **Description:** Create `RanaLayerDataItem` — always a leaf. Icon mapped from `layer.type` using QGIS theme icons:
  - Point / MultiPoint → `mIconPointLayer.svg`
  - LineString / MultiLineString → `mIconLineLayer.svg`
  - Polygon / MultiPolygon → `mIconPolygonLayer.svg`
  - GeometryCollection → `mIconGeometryCollectionLayer.svg`
  - raster → `mIconRaster.svg`
  - null / unknown → generic file icon

  Wire `RanaFileDataItem.createChildren()` to fetch the file descriptor via `GET /tenants/{tenant_id}/file-descriptors/{file_descriptor_id}` and return `RanaLayerDataItem` instances from `descriptor["layers"]`. Error handling follows same pattern. No context menu yet.
- **Depends on:** Task 4
- **Acceptance:** Expanding a vector file shows its layers with correct geometry-type icons
- **Evidence:** Manual test: expand a vector file → layers appear with correct icons

### Context Menus

#### Task 6: `file_actions.py` + all context menus
- **Estimate:** ~80 lines
- **Files:** `rana_qgis_plugin/data_items/file_actions.py` (new), `rana_qgis_plugin/data_items/files_item.py`, `rana_qgis_plugin/data_items/folder_item.py`, `rana_qgis_plugin/data_items/file_item.py`, `rana_qgis_plugin/data_items/layer_item.py`, `tests/test_file_actions.py` (new)
- **Description:** Create `file_actions.py` with a `FileAction` enum (subset of legacy: `OPEN_IN_QGIS`, `OPEN_WMS`, `DOWNLOAD_RESULTS`, `OPEN_IN_BROWSER`, `RENAME`, `DELETE`), icon and tooltip dicts copied from `legacy/widgets/utils_file_action.py` (no legacy imports), and two functions:
  - `get_file_actions(data_type: str) -> list[FileAction]` — returns actions per the design matrix; for scenario types `OPEN_WMS` and `DOWNLOAD_RESULTS` are included as static placeholders (descriptor fetch deferred to when actions are connected)
  - `get_folder_actions(is_root: bool = False) -> list[FileAction]` — returns folder actions; omits Delete when `is_root=True`

  Wire context menus into all four item types. All actions are **unconnected** (no `triggered` handlers). For folders/files root: Refresh, Create directory, Upload file(s), Version history, Open in web, [separator], Delete (folders only). For files: per action matrix with separator before Delete. For layers: Open in QGIS only.
- **Depends on:** Task 5
- **Acceptance:** Right-clicking each item type shows the correct menu entries per the design; actions present but not wired
- **Evidence:** Manual test: right-click each item type → correct entries appear; unit tests for `get_file_actions()` and `get_folder_actions()` pass

## Notes

- `get_tenant_project_files()` is the shared file-listing API helper. Its error behavior changes to propagate `FetchError`; legacy callers are allowed to be updated or broken as part of this feature.
- All `createChildren()` implementations follow the error handling pattern from `rana_item.py:92-99`
- Context menu actions are present but intentionally unconnected in this feature; wiring is a future task
- Scenario descriptor fetch (for Open WMS / Download results) is deferred to when those actions are connected
- Pre-loading next level for perceived performance is a future optimization if lazy loading proves too slow

## Progress

- [x] Task 1: API helper — paginated file listing
- [x] Task 2: `RanaFilesDataItem` + wire into `RanaProjectDataItem`
- [x] Task 3: `RanaFolderDataItem`
- [x] Task 4: `RanaFileDataItem`
- [x] Task 5: `RanaLayerDataItem`
- [x] Task 6: `file_actions.py` + all context menus
