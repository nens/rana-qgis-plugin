---
feature: feat_455_open_wms
status: planned
created: 2026-09-21
chunk_size: adaptive
total_tasks: 5
estimated_lines: ~400
---

# Open WMS for Scenarios Tasks

## Overview

Implement the remaining Open WMS part of Task 455. The feature adds a
context-menu action for one scenario and multi-select scenario selections. It
does not add folder-level Open WMS yet. It creates remote WMS raster layers
from scenario descriptors without downloading result files. WMS layers are
placed below a dedicated `wms` group under the scenario path, for example
`path/to/scenario/wms`.

The implementation follows the current module-level layer-opening functions,
shares single and batch loader behavior, and keeps folder resolution lazy.

## Task List

### Foundation

#### Task 1: Verify layer-manager usage and add `open_rana_wms` [P]
- **Estimate:** ~100 lines, including tests
- **Parallel:** Can start independently of Task 2
- **Files:** `rana_qgis_plugin/layer_management/layer_manager.py`, `tests/test_layer_manager.py` or the repository's closest existing layer-management test module
- **Description:** First search all active-plugin imports and references to the old `LayerManager`, `FileLayerManager`, and `PublicationLayerManager` hierarchy. Define the `open_rana_wms` module-level function using the legacy URI parameters and current group helpers (`find_or_create_rana_groups` and `add_layer_to_group`). The function receives a complete parent path whose final segment is `wms`; the Loader will construct the path as project/files + scenario ID parts + `wms`. Create one `QgsRasterLayer` per descriptor layer, add only valid layers, and return the layers added. Do not apply `RanaLayerRef` or dirty tracking to WMS layers. Do not delete the old hierarchy in this task unless the reference check proves that deletion is safe and keeps the resulting change easy to review.
- **Depends on:** None
- **Acceptance:** A descriptor WMS link and layer list produce valid WMS raster layers in the supplied `.../wms` group, with the expected URI parameters and no Rana reference metadata. Missing/invalid layer construction does not add invalid layers.
- **Evidence:** Focused layer-manager tests pass; import/reference search identifies all remaining uses of the old classes.

### Core Implementation

#### Task 2: Add the request model and shared Loader WMS flow
- **Estimate:** ~120 lines, including tests
- **Files:** `rana_qgis_plugin/utils/data_models.py`, `rana_qgis_plugin/loader.py`, `tests/test_loader_wms.py` or the repository's closest Loader test module
- **Description:** Add frozen `OpenScenarioWmsRequest(project, file_item)`. Add dedicated `Loader.open_scenario_wms(request)` and `Loader.open_scenario_wms_batch(requests)` methods; do not add WMS requests to the general `open_items()` union or dispatcher. The shared per-scenario helper fetches the descriptor, validates the WMS link and descriptor layers, builds the parent path as project/files + scenario ID parts + `wms`, and calls `open_rana_wms`. The batch method iterates requests and invokes that helper once per scenario. Keep processing synchronous. A failure for one batch item must not abort later items; return/track enough outcome information for summary feedback in the UI integration task.
- **Depends on:** Task 1
- **Acceptance:** A valid request opens all valid descriptor WMS layers. Missing descriptor, missing WMS link, empty layer list, and invalid layer cases produce controlled outcomes without unhandled exceptions. Batch processing invokes the same per-scenario path for every request and isolates failures.
- **Evidence:** Loader unit tests cover valid single, invalid descriptor metadata, and multi-request failure isolation; targeted test command passes.

#### Task 3: Wire single-file and multi-select context-menu actions
- **Estimate:** ~80 lines, including tests
- **Files:** `rana_qgis_plugin/data_items/file_item.py`, `rana_qgis_plugin/data_items/gui_provider.py`, `rana_qgis_plugin/data_items/file_actions.py` if dispatch adjustments are needed, relevant data-item tests
- **Description:** Connect `FileAction.OPEN_WMS` in `RanaFileDataItem.actions()` to `Loader.open_scenario_wms()` using `OpenScenarioWmsRequest`. Add `OPEN_WMS` to `MULTI_SELECT_ACTIONS` and create the multi-select dispatch to `Loader.open_scenario_wms_batch()`. Do not route WMS through `Loader.open_items()`. Preserve the existing double-click result-opening behavior. Rely on the existing action intersection logic so a mixed file selection does not expose Open WMS.
- **Depends on:** Task 2
- **Acceptance:** A single scenario context-menu action creates one WMS request. A selection containing only scenarios exposes Open WMS and dispatches all scenarios. A mixed selection does not expose Open WMS. Double-click still opens scenario results.
- **Evidence:** Data-item/provider tests pass for single action wiring, all-scenario multi-select, mixed selection gating, and unchanged double-click behavior.

#### Task 4: Verify Open WMS scope boundaries
- **Estimate:** ~35 lines, including tests
- **Files:** `rana_qgis_plugin/data_items/file_actions.py`, `rana_qgis_plugin/data_items/folder_item.py`, relevant action tests
- **Description:** Verify that Open WMS is exposed for scenario files and scenario-only multi-selections, but not for folders. Keep normal folder Open in QGIS behavior unchanged. Confirm single and batch WMS failures produce controlled message-bar feedback through the shared Loader flow. Do not add folder resolution or folder-specific WMS state.
- **Depends on:** Task 3
- **Acceptance:** Folder actions do not contain `OPEN_WMS`; file actions and scenario-only multi-select actions still do. Normal folder opening remains available.
- **Evidence:** Focused file-action/provider/Loader tests pass and no folder WMS entry point exists in active code.

### Integration & Cleanup

#### Task 5: Remove obsolete WMS class code and verify integration
- **Estimate:** ~70 lines, mostly deletion and verification
- **Files:** `rana_qgis_plugin/layer_management/layer_manager.py`, tests or documentation only if required by the verification
- **Description:** Re-run the active-code reference search from Task 1 after the new flow is wired. If no active code uses the old `LayerManager`, `FileLayerManager`, or `PublicationLayerManager` hierarchy, delete the obsolete hierarchy and any imports that become unused. Keep legacy reference files untouched. Run formatting/static checks and the focused test suite. Record any references that require deferring deletion rather than removing code speculatively.
- **Depends on:** Tasks 1–4
- **Acceptance:** Active plugin code contains no dependency on the obsolete class hierarchy, the new module-level WMS path is the only active scenario-WMS implementation, and no unrelated layer-opening behavior regresses.
- **Evidence:** Targeted unit tests pass, `git diff --check` passes, import/reference search confirms the intended cleanup, and the relevant test suite completes successfully.

## Dependencies and Parallelization

- Task 1 is independent and can run in parallel with initial model/test preparation for Task 2, but Task 2's implementation depends on the final `open_rana_wms` interface.
- Tasks 3 and 4 are sequential because Task 4 verifies the final UI scope after Task 3's action wiring.
- Task 5 must wait until all active references have been checked after integration; deletion is intentionally last.

## Testing Strategy

- Bundle focused unit tests with each implementation task.
- Test real layer/group behavior where the repository's QGIS test fixtures support it; avoid tests that only assert mocked calls.
- Do not add E2E tests without explicit permission.
- Manual UI verification is required after implementation:
  - Scenario → context menu → **Open WMS in QGIS**.
  - Multiple scenarios → context menu → **Open WMS in QGIS**.
  - Mixed file selection → Open WMS is unavailable.
  - Folder → context menu → confirm **Open WMS in QGIS** is unavailable; normal **Open in QGIS** remains available.
  - Scenario double-click remains the result-download/open flow.

## Notes

- Use the legacy implementation as a behavior reference only; do not copy its
  class/threading architecture.
- WMS layers are remote and intentionally do not receive `RanaLayerRef` or
  dirty tracking.
- Keep descriptor fetching synchronous because this feature performs metadata
  retrieval and layer construction only; revisit threading only if profiling
  shows the operation can freeze the UI.
- Folder-level Open WMS is deferred to a future feature.
- The design records are referenced from `design.md` and should remain aligned
  with any implementation changes.

## Progress

- [x] Task 1: Verify layer-manager usage and add `open_rana_wms`
- [x] Task 2: Add the request model and shared Loader WMS flow
- [x] Task 3: Wire single-file and multi-select context-menu actions
- [ ] Task 4: Verify Open WMS scope boundaries
- [ ] Task 5: Remove obsolete WMS class code and verify integration
