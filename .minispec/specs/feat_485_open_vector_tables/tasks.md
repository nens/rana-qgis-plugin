---
feature: feat_485_open_vector_tables
status: planned
created: 2026-10-12
chunk_size: adaptive
total_tasks: 6
estimated_lines: 500
---

# Open Vector Tables Tasks

## Overview

Implement the approved design in `design.md`: discover Browser layers and
tables from descriptor metadata and open selected layers/tables through one
request flow. Whole-file opening currently treats the downloaded GeoPackage
as authoritative; whether to filter it using descriptor metadata is pending
PM/designer input.

Implementation should reuse the current Browser item, loader, OGR, layer
reference, and error-reporting patterns. Add/extend unit tests alongside each
implementation task. Do not add E2E tests without explicit approval.

## Task List

### Foundation and Browser discovery

#### Task 1: Add unified selected-vector request models
- **Estimate:** ~40–70 lines
- **Files:** `rana_qgis_plugin/utils/data_models.py`
- **Description:** Add immutable `VectorLayerRef` and `VectorTableRef` value
  objects and `OpenVectorFileRequest` containing project, parent file, and a
  tuple of either child reference.
- **Depends on:** None
- **Acceptance:** Both child types can be represented in one request without
  losing their names or child IDs.
- **Evidence:** The model module compiles; selected-vector request behavior is
  verified in Task 5's aggregation and loader tests.

#### Task 2: Add the table Browser item and native icon mapping
- **Estimate:** ~50–90 lines
- **Files:** `rana_qgis_plugin/data_items/table_item.py` (new),
  `rana_qgis_plugin/utils/generic.py`, `tests/utils/test_generic.py`
- **Description:** Implement a leaf `RanaTableDataItem`, using
  `mIconTableLayer.svg` through the existing icon mechanism. Its open action
  sends a one-child `OpenVectorFileRequest`.
- **Depends on:** Task 1
- **Acceptance:** A leaf table item can be constructed and uses the native
  table icon mapping.
- **Evidence:** The generic icon mapping test passes; table action behavior is
  exercised with selected-child flow in Task 5.

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
- **Evidence:** Implementation review confirms Browser discovery reads the
  descriptor's `meta` fields; no dict-shape-only test was retained.

### Selected-child opening

#### Task 4: Open an individual geometryless table
- **Estimate:** ~40–80 lines
- **Files:** `rana_qgis_plugin/layer_management/layer_manager.py`,
  `tests/test_layer_manager.py`
- **Description:** Add table opening using an OGR GeoPackage layer URI; reject
  invalid layers, attach the existing Rana layer reference with `table_id`,
  and reuse current group, dirty-tracking, and layer-add behavior where
  appropriate.
- **Depends on:** None; can proceed after Task 1
- **Acceptance:** A valid geometryless table opens with the expected Rana
  reference; an invalid table is not added.
- **Evidence:** Layer-manager tests verify valid and invalid table behavior.

#### Task 5: Unify selected-vector aggregation and opening
- **Estimate:** ~120–180 lines
- **Files:** `rana_qgis_plugin/data_items/layer_item.py`,
  `rana_qgis_plugin/data_items/table_item.py`,
  `rana_qgis_plugin/data_items/gui_provider.py`,
  `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/utils/data_models.py`,
  `tests/data_items/test_gui_provider.py`, `tests/loader/test_mixed_opening.py`
- **Description:** Use `OpenVectorFileRequest` for every selected-vector
  request, whether it contains only layers, only tables, or both. Aggregate
  children into exactly one request per parent file; remove `OpenLayersRequest`
  and the conditional request-type branch. Make the loader dispatch child refs
  after one download, merge duplicate child requests for the same file, and
  preserve whole-file `OpenFileRequest` subsumption. Wire table item opening
  to the same request.
- **Depends on:** Tasks 1–4
- **Acceptance:** Layer-only, table-only, and mixed selections each produce
  one `OpenVectorFileRequest` per parent; loader opens the requested children
  after one download; duplicate requests merge; whole-file requests subsume
  selected-vector requests regardless of order.
- **Evidence:** GUI-provider and loader tests pass for request aggregation,
  child dispatch, single download, merging, and whole-file precedence.

### Complete-file opening

#### Task 6: Revisit whole-file authority after product/design decision
- **Estimate:** ~60–100 lines
- **Files:** To be determined after the policy decision
- **Description:** The current implementation opens sublayers discovered in
  the downloaded GeoPackage, including geometryless tables. Await PM/designer
  decision on whether the descriptor should filter whole-file contents before
  changing this behavior.
- **Depends on:** PM/designer decision on authority
- **Acceptance:** Update the design and implementation only after the policy
  is confirmed; if descriptor-authoritative, open listed items only and report
  missing listed tables while continuing with available contents.
- **Evidence:** Product/design decision is documented and the resulting
  whole-file behavior is covered by focused tests.

## Dependencies & Execution Order

- Task 1 is the foundation.
- Task 2 depends on Task 1; Task 3 depends on Task 2.
- Task 4 (table layer-manager primitive) can proceed after Task 1, in parallel
  with Browser work.
- Task 5 integrates all selected-child paths and depends on Tasks 1–4.
- Task 6 is deferred until the PM/designer decide whether the GeoPackage or
  descriptor is authoritative for whole-file opening.
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

- [x] Task 1: Add unified selected-vector request models (no standalone model
  test retained per engineer review)
- [x] Task 2: Add the table Browser item and native icon mapping
- [x] Task 3: Discover children from descriptor `meta`
- [x] Task 4: Open an individual geometryless table
- [x] Task 5: Unify selected-vector aggregation and opening
- [ ] Task 6: Revisit whole-file authority after product/design decision
  (deferred; GeoPackage is authoritative for now)
