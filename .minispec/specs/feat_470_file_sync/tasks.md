---
feature: feat_470_file_sync
status: planned
created: 2026-10-14
chunk_size: adaptive
total_tasks: 6
estimated_lines: 520
---

# Unsynced Rana Changes Visibility Tasks

## Overview

Implements `.minispec/specs/feat_470_file_sync/design.md`: show dirty-state
badges in the QGIS layer tree and prompt to sync dirty Rana-linked files when
the project is cleared. Estimates include implementation and focused unit
tests; UI paths require manual verification as noted below.

## Task List

### Foundation

#### Task 1: Add Loader sync-completion notification (superseded)
- **Estimate:** ~35 lines
- **Files:** `rana_qgis_plugin/loader.py`, `tests/loader/test_upload.py`
- **Description:** Add `Loader.rana_sync_completed = pyqtSignal(list)`. In
  `handle_sync_completed`, collect the affected layers and emit them only
  when the sync succeeded and was not cancelled, alongside clearing the
  corresponding dirty flag. The signal supports indicator refresh; it does
  not coordinate or block close-time uploads.
- **Depends on:** None
- **Acceptance:** Successful style/data sync emits the relevant layers after
  clearing their flags; a failed or cancelled sync does not emit a success
  signal or clear those flags.
- **Evidence:** Focused loader tests cover successful emission and no emission
  for failure/cancellation; existing upload tests pass.

### Core Implementation

#### Task 2: Use native property notifications for layer-level indicators
- **Estimate:** ~150 lines (implementation, tests, and signal cleanup)
- **Files:** `rana_qgis_plugin/layer_management/indicator_manager.py` (new),
  `tests/layer_management/test_indicator_manager.py` (new),
  `rana_qgis_plugin/loader.py`, `tests/loader/test_upload.py`
- **Description:** Implement an `IndicatorManager` that attaches one generic
  `QgsLayerTreeViewIndicator` to dirty Rana-linked layer nodes. Initialize
  tracking for layers added to the project while the plugin is running, and
  listen to `QgsMapLayer.customPropertyChanged(key)` for the existing dirty
  property keys. Do not duplicate listeners to `afterCommitChanges` or
  `styleChanged`: `dirty_tracking.py` already owns those signals and writes
  the properties. Property removal after sync uses the same notification.
  Remove the now-redundant `Loader.rana_sync_completed` signal added in the
  superseded Task 1 implementation. Scanning layers already present when the
  plugin starts is not required. Use a QGIS theme icon rather than adding a
  new asset.
- **Depends on:** Task 1 (remove its superseded signal while completing this
  task)
- **Acceptance:** A linked vector layer receives a badge after a committed
  data edit or style change; a clean or non-Rana layer does not. A linked layer
  added after the manager starts is tracked and receives its badge when dirty.
- **Evidence:** Tests use real QGIS layer objects and the `qgis_application`
  fixture; focused indicator-manager tests pass.

#### Task 3: Aggregate indicators and keep their lifecycle current
- **Estimate:** ~130 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/layer_management/indicator_manager.py`,
  `tests/layer_management/test_indicator_manager.py`
- **Description:** Extend `IndicatorManager` to add one aggregate badge to
  ancestor group nodes while any descendant linked layer is dirty. Remove or
  retain group badges correctly as individual layers become clean/dirty;
  remove indicators when associated layer/group nodes are removed; clean up
  all indicators and signal connections when the manager disconnects. Connect
  to the native `customPropertyChanged` signal for dirty-flag removals and
  re-evaluate affected layers/groups.
- **Depends on:** Task 2
- **Acceptance:** A dirty child marks its ancestors; cleaning one of multiple
  dirty children does not clear the aggregate badge prematurely; cleaning the
  last dirty child clears it. Removed nodes and plugin teardown leave no
  registered indicators or active manager connections.
- **Evidence:** Focused tests cover aggregation, mixed dirty/clean descendants,
  dirty-property removal, node removal, and disconnect cleanup.

#### Task 4: Collect dirty file groups for close-time sync
- **Estimate:** ~90 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/layer_management/close_sync_prompt.py` (new),
  `rana_qgis_plugin/layer_management/layer_tree_menu.py`,
  `tests/layer_management/test_close_sync_prompt.py` (new)
- **Description:** Add a testable scanning function that walks the layer-tree
  root and returns separate file-group lists for style-dirty and data-dirty
  content. Reuse `LayerTreeMenuProvider.file_groups` and
  `_collect_all_layers`; rename `_collect_all_layers` to
  `collect_all_layers` as specified by the design. Ignore non-Rana and clean
  layers, and do not treat rasters as data-dirty.
- **Depends on:** None
- **Acceptance:** The scan returns only groups containing the relevant dirty
  flags, handles groups with multiple layers without duplicate groups, and
  excludes raster data from the data-dirty result.
- **Evidence:** Focused tests construct real layer-tree groups/layers and
  exercise clean, style-dirty, vector-data-dirty, raster, and nested-group
  cases.

### Integration & Verification

#### Task 5: Prompt and dispatch sync before project clearing
- **Estimate:** ~75 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/layer_management/close_sync_prompt.py`,
  `tests/layer_management/test_close_sync_prompt.py`
- **Description:** Add a connect/disconnect lifecycle for
  `QgsProject.instance().aboutToBeCleared`. When dirty groups are found, show
  a dialog listing affected files with exactly “Sync now” and “Continue
  without syncing” choices. Do not show a dialog when the scan is empty. On
  “Sync now,” invoke the existing `LayerTreeMenuProvider.save_style` and
  `save_data` with only their corresponding dirty groups; do not add a
  blocking wait or new upload orchestration.
- **Depends on:** Task 4
- **Acceptance:** The hook is silent for a clean project, presents the two
  correct choices when dirty groups exist, dispatches only selected dirty
  groups on “Sync now,” and disconnects cleanly.
- **Evidence:** Focused tests verify scan-to-dialog decisions and delegation;
  manually test switching/closing a project with dirty linked layers and
  quitting QGIS with dirty linked layers. Confirm a clean project shows no
  prompt.

#### Task 6: Wire managers into plugin lifecycle and verify the feature
- **Estimate:** ~60 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/rana_qgis_plugin.py`,
  relevant plugin/layer-management tests
- **Description:** Construct the indicator manager and close-sync prompt with
  the existing `Loader`, interface, and `LayerTreeMenuProvider`; connect them
  in `initGui` and disconnect/clean up in `unload`, following the existing
  `layer_tree_menu` and `local_linking` lifecycle pattern.
- **Depends on:** Tasks 3 and 5
- **Acceptance:** Layers added while the plugin is running are tracked, and
  new edits and successful syncs update badges. Unload disconnects both
  integrations. Existing plugin behavior remains intact.
- **Evidence:** Focused tests verify lifecycle wiring where feasible; relevant
  unit tests pass. Manual UI paths: edit a Rana-linked vector layer, change a
  linked layer's style, collapse/expand its containing groups, sync via the
  context menu, close/switch projects, and quit QGIS with dirty changes.

## Dependencies & Parallel Opportunities

- Task 1's Loader-signal approach is superseded; Task 2 removes that signal
  while implementing the layer-level indicator using property notifications.
- Tasks 2 and 4 touch separate code areas and can be implemented in parallel.
- Task 3 depends on Task 2's indicator-manager foundation.
- Task 5 depends on Task 4's dirty-group scan.
- Task 6 integrates the finished indicator manager and close-sync prompt, so
  it depends on Tasks 3 and 5.
- No task adds E2E tests; those require separate explicit permission per the
  repository testing policy.

## Notes

- Dirty indicators rely on `QgsMapLayer.customPropertyChanged` for both dirty
  property additions and removals; no new Loader signal is needed.
- Schematisation dirty tracking and individual layer-removal warnings remain
  out of scope.
- The close warning cannot cancel project clearing. “Continue without
  syncing” is intentionally not labeled “Cancel.”

## Progress

- [x] Task 1: Add Loader sync-completion notification (superseded)
- [x] Task 2: Use native property notifications for layer-level indicators
- [x] Task 3: Aggregate indicators and keep their lifecycle current
- [x] Task 4: Collect dirty file groups for close-time sync
- [ ] Task 5: Prompt and dispatch sync before project clearing
- [ ] Task 6: Wire managers into plugin lifecycle and verify the feature
