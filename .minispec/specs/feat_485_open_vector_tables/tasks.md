---
feature: feat_485_open_vector_tables
status: planned
created: 2026-10-12
chunk_size: adaptive
total_tasks: 7
estimated_lines: 450
---

# Open Vector Tables Tasks

## Overview

Implement the approved design in `design.md`: discover vector layers from
`meta["layers"]`, show descriptor-listed tables as flat Browser siblings, open
selected layers and tables through one request flow, and include supported
tables when opening a complete vector file.

Implementation should reuse the current Browser item, loader, OGR, layer
reference, and error-reporting patterns. Add/extend unit tests alongside each
implementation task. Do not add E2E tests without explicit approval.

## Task List

### Foundation and Browser discovery

#### Task 1: Add unified vector-child request models
- **Estimate:** ~40–70 lines
- **Files:** `rana_qgis_plugin/utils/data_models.py`
- **Description:** Add immutable `VectorLayerRef` and `VectorTableRef` value
  objects and `OpenVectorChildrenRequest` containing project, parent file,
  and a tuple of either child reference. Keep the existing `OpenLayersRequest`
  until Task 6 migrates its callers.
- **Depends on:** None
- **Acceptance:** Both child types can be represented in one request without
  losing their names or child IDs.
- **Evidence:** The model module compiles, and the existing selected-layer
  request tests continue to pass while migration is deferred to Task 6.

#### Task 2: Add the table Browser item and native icon mapping
- **Estimate:** ~50–90 lines
- **Files:** `rana_qgis_plugin/data_items/table_item.py` (new),
  `rana_qgis_plugin/utils/generic.py`, `tests/utils/test_generic.py`
- **Description:** Implement a leaf `RanaTableDataItem`, using
  `mIconTableLayer.svg` through the existing icon mechanism. The selected-table
  opening action is deferred until Task 6, when the loader accepts the unified
  request type.
- **Depends on:** Task 1
- **Acceptance:** A leaf table item can be constructed and uses the native
  table icon mapping.
- **Evidence:** The generic icon mapping test passes; the item is exercised
  when Browser discovery is covered in Task 3.

#### Task 3: Discover children from descriptor `meta`
- **Estimate:** ~40–80 lines
- **Files:** `rana_qgis_plugin/data_items/file_item.py`,
  `tests/data_items/test_file_item.py`
- **Description:** Build layer children from `descriptor["meta"]["layers"]`
  (not the root-level `descriptor["layers"]`) and flat table siblings from
  `descriptor["meta"]["tables"]`, using each table record's `table_id`.
  Preserve current descriptor-fetch error behavior and layer-only behavior.
- **Depends on:** Task 2
- **Acceptance:** A descriptor with different root and `meta` layers yields
  children from `meta`; tables appear as siblings; descriptors with no tables
  still show their layers.
- **Evidence:** File-item tests cover mixed children, authoritative `meta`,
  no tables, and existing fetch-error handling.

### Selected-child opening

#### Task 4: Open an individual geometryless table
- **Estimate:** ~40–80 lines
- **Files:** `rana_qgis_plugin/layer_management/layer_manager.py`,
  `tests/test_layer_manager.py`
- **Description:** Add table opening using an OGR GeoPackage layer URI; reject
  invalid layers, attach the existing Rana layer reference with `table_id`,
  and reuse current group, dirty-tracking, and layer-add behavior where
  appropriate.
- **Depends on:** None; can proceed in parallel with Task 5 after Task 1
- **Acceptance:** A valid geometryless table opens with the expected Rana
  reference; an invalid table is not added.
- **Evidence:** Layer-manager tests verify valid and invalid table behavior.

#### Task 5: Aggregate selected layers and tables by parent file
- **Estimate:** ~40–80 lines
- **Files:** `rana_qgis_plugin/data_items/gui_provider.py`,
  `tests/data_items/test_gui_provider.py`
- **Description:** Extend selection aggregation to include both
  `RanaLayerDataItem` and `RanaTableDataItem`, producing one unified
  `OpenVectorChildrenRequest` per parent vector file.
- **Depends on:** Tasks 1–3
- **Acceptance:** Layer-only, table-only, and mixed selections are grouped by
  parent file without duplicate file requests.
- **Evidence:** GUI-provider tests cover same-file aggregation and separate
  files.

#### Task 6: Download once and dispatch selected vector children
- **Estimate:** ~60–100 lines
- **Files:** `rana_qgis_plugin/data_items/layer_item.py`,
  `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/utils/data_models.py`,
  `tests/loader/test_mixed_opening.py`, relevant data-item tests
- **Description:** Migrate the existing selected-layer caller and loader from
  `OpenLayersRequest` to `OpenVectorChildrenRequest`. Dispatch `VectorLayerRef`
  and `VectorTableRef` after downloading each parent once. Preserve
  `OpenFileRequest` precedence so a whole-file request subsumes child
  requests. Remove `OpenLayersRequest` if no remaining callers use it.
- **Depends on:** Tasks 4–5
- **Acceptance:** Selected layers, tables, and mixed children open after one
  download per file; whole-file requests still subsume selected-child
  requests regardless of request order.
- **Evidence:** Loader and layer-item tests pass, including download count and
  file-request precedence cases.

### Complete-file opening

#### Task 7: Include descriptor-listed tables in open-all
- **Estimate:** ~60–100 lines
- **Files:** `rana_qgis_plugin/layer_management/layer_manager.py`,
  `tests/test_layer_manager.py`
- **Description:** Extend complete vector-file opening to inspect local
  provider sublayers and open descriptor-listed tables that are actually
  present. Ignore unlisted geometryless sublayers. Report descriptor-listed
  tables missing locally using the existing layer-opening failure mechanism,
  skip them, and continue with remaining valid children.
- **Depends on:** Task 4
- **Acceptance:** Full-file opening adds available listed layers and tables,
  ignores unlisted tables, and reports/skips a missing listed table while
  continuing with remaining contents.
- **Evidence:** Layer-manager tests verify listed/missing/unlisted table
  behavior with a GeoPackage fixture or the repository's established QGIS
  provider test pattern.

## Dependencies & Execution Order

- Task 1 is the foundation.
- Tasks 2 and the initial work on Task 4 can proceed independently after Task
  1 (Task 4's implementation uses the reference metadata contract).
- Task 3 depends on Task 2; Task 5 depends on Tasks 1–3.
- Task 6 integrates selected-child paths and depends on Tasks 4–5.
- Task 7 depends on Task 4 and can be implemented before or after Task 6.
- No task changes the deferred `relation_name` behavior.

## Notes

- `table_id` is assumed stable across reprocessing and is reused as
  `RanaLayerRef.layer_id`.
- Table items are flat siblings; `layer_id` and `columns` are ignored.
- Browser layer discovery must use `descriptor["meta"]["layers"]` rather
  than the root-level `layers` field.
- Use the native QGIS `mIconTableLayer.svg` icon.
- UI paths requiring manual testing: expand a vector file in the Browser, open
  one table, open a mixed layer/table selection, open a whole vector file, and
  open a folder containing vector files.

## Progress

- [x] Task 1: Add unified vector-child request models (existing layer request
  retained temporarily for compatibility until Task 6 migrates its callers;
  no standalone model test retained per engineer review)
- [x] Task 2: Add the table Browser item and native icon mapping (opening
  action intentionally deferred to Task 6)
  (selected-table opening action is deferred to Task 6)
- [ ] Task 3: Discover children from descriptor `meta`
- [ ] Task 4: Open an individual geometryless table
- [ ] Task 5: Aggregate selected layers and tables by parent file
- [ ] Task 6: Download once and dispatch selected vector children
- [ ] Task 7: Include descriptor-listed tables in open-all
