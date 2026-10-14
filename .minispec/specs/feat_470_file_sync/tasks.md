---
feature: feat_470_file_sync
status: in_progress
created: 2026-10-14
chunk_size: adaptive
total_tasks: 15
estimated_lines: 1415
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
  corresponding dirty state. The signal supports indicator refresh; it does
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
  `styleChanged`: `layer_dirty_flags.py` already owns those signals and writes
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

#### Task 5: Prompt and dispatch sync before project clearing or layer removal
- **Estimate:** ~150 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/layer_management/close_sync_prompt.py`,
  `tests/layer_management/test_close_sync_prompt.py`
- **Description:** Keep the project-clear prompt and add a prompt before
  removing dirty Rana-linked layers/groups. Use project pre-removal and
  layer-tree pre-detach signals, collect dirty descendants for a removed
  group as one file-group set, and deduplicate overlapping tree/project
  notifications. Suppress per-layer prompts during project clear. Use the
  same “Sync now” / “Continue without syncing” choice and existing
  `LayerTreeMenuProvider.save_style`/`save_data` methods; do not add blocking
  waits or new upload orchestration.
- **Depends on:** Task 4
- **Acceptance:** Clean project/layer/group removal is silent. Dirty individual
  layer removal prompts once. Removing a group with multiple dirty descendants
  shows one prompt and dispatches each affected file group once. Project clear
  shows only its single project-level prompt. “Sync now” dispatches only dirty
  groups; all signals disconnect cleanly.
- **Evidence:** Focused tests cover single-layer removal, multi-layer group
  removal, project-clear deduplication, clean-state no-op, and sync delegation.
  E2E covers dirty layer removal and project clear. Manually test removing a
  dirty layer, removing a group with multiple dirty layers, switching/closing
  a project with dirty linked layers, and quitting QGIS with dirty linked
  layers.

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

## Follow-up: dirty-state correctness

Tasks 1-6 delivered the feature; manual testing then surfaced KI-001 to
KI-008 in the design. Tasks 7-10 address KI-002, KI-003 and KI-004, and
establish the shared `UNKNOWN` policy for KI-007. Tasks 11-15 implement
filesystem-based dirty detection for eligible Rana rasters, closing the
remaining raster tracking gap in KI-007. KI-001, KI-005, KI-006 and KI-008
remain open and out of scope.

**Scope decision, 2026-10-21.** An earlier draft included a style-fingerprint
mechanism (former Tasks 8-10, ~345 lines) to close the KI-001 detection holes.
It is deferred — see the `rejected-for-now` status in
`../../knowledge/decisions/20261021-style-fingerprint-dirty-detection.md`,
which records the two triggers that would revive it. `styleChanged` remains
the detection mechanism for styles; the existing tasks concern how dirtiness
is *interpreted and propagated*.

**Raster tracking decision, 2026-10-21.** Raster dirty state is derived from a
stat-based fingerprint of the main raster source file uploaded to Rana. The
baseline lives on the layer as `rana/data_fingerprint`; the cached sync status
is stored in `rana/data_sync_state`. Neither is in QSettings. See
`../../knowledge/decisions/20261021-raster-file-fingerprint-dirty-detection.md`.

Run tests with `docker compose run --rm qgis pytest -v tests` (README,
"Local development notes"). Scope to a file while iterating, e.g.
`... pytest -v tests/layer_management/test_layer_sync_state.py`.

### Shared convention: where the predicates live

`is_rana_linked` lives in `layer_manager.py`, and `layer_manager.py` imports
`attach_dirty_tracking` from `layer_dirty_flags.py`. Putting linking-aware
predicates into `layer_dirty_flags.py` would create the import cycle
`layer_manager → layer_dirty_flags → layer_manager`. Split the concerns:

- `layer_dirty_flags.py` stays **low-level**: raw custom-property reads/writes
  and signal attachment. It must not import `layer_manager`.
- `layer_sync_state.py` holds the **consumer-visible** predicates and the
  `LayerSyncState` enum. It imports `is_rana_linked` from `layer_manager` and
  raw predicates from `layer_dirty_flags`. Consumers import only from here.
- `raster_dirty_evaluator.py` imports the `LayerSyncState` enum from
  `layer_sync_state.py` and returns it directly, so raster and vector dirty
  state share one vocabulary. It does not import `layer_sync_state.py`'s
  predicate functions, so there's no cycle back the other way.

Resulting order, acyclic: `layer_sync_state → {layer_manager,
layer_dirty_flags}`, `layer_manager → layer_dirty_flags`, and
`raster_dirty_evaluator → {layer_dirty_flags, layer_sync_state}`.

Do not add linking checks to the existing `is_data_dirty` / `is_style_dirty`
in `layer_dirty_flags.py`. They are storage primitives, used by tracking
internals and by `clear_dirty`, which must still work on a layer that has
since been unlinked. Only `layer_sync_state.py` applies `is_rana_linked`.

#### Task 7: Define one shared dirty state

- **Estimate:** ~150 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/layer_management/layer_sync_state.py` (new),
  `layer_tree_menu.py`, `close_sync_prompt.py`, `indicator_manager.py`,
  `tests/layer_management/test_layer_sync_state.py` (new)
- **Description:** Create `layer_sync_state.py` with this exact API:

  ```python
  class LayerSyncState(Enum):
      CLEAN = auto()
      DIRTY = auto()
      UNKNOWN = auto()      # cannot determine the data state


  def layer_sync_state(layer: QgsMapLayer) -> LayerSyncState: ...
  def has_unsynced_style(layer: QgsMapLayer) -> bool: ...
  def should_badge(layer: QgsMapLayer) -> bool: ...
  ```

  `layer_sync_state` returns `CLEAN` for unlinked layers, `UNKNOWN` for
  `QgsRasterLayer` (until Tasks 11-15 provide an evaluator), else
  `DIRTY`/`CLEAN` from `is_data_dirty`.
  `has_unsynced_style` is `is_rana_linked and is_style_dirty`.
  `should_badge` is the badge's single combine rule:
  `has_unsynced_style(layer) or layer_sync_state(layer) is DIRTY` — note
  `UNKNOWN` never badges.

  Data-state raster checks belong **only** in `layer_sync_state.py`. Preserve
  unrelated raster checks, such as `layer_tree_menu.py:155`, which selects
  the upload data type rather than interpreting dirty state. Replace these
  existing expressions:

  - `layer_tree_menu.py:117-122` — `all_layers = self.collect_all_layers([node])`,
    the `is_style_dirty` any(), and `isinstance(layer, QgsRasterLayer) or
    is_data_dirty(layer)`. Menu enablement becomes: style action on
    `any(has_unsynced_style(l) ...)`, data action on
    `any(layer_sync_state(l) is not CLEAN ...)`. Keep the existing `locked`
    check unchanged. Evaluating all descendants of the selected group is
    intended and stays; the fix is that each layer is now linking-filtered.
  - `close_sync_prompt.py:37-48` — the `rana_layers` filter and the raster
    check at `:45`.
  - `close_sync_prompt.py:159-162`, `:183-186`, `:200` — further independent
    combinations of `is_rana_linked` with dirty flags during removal and
    deduplication. These must be consolidated too; missing them leaves the
    predicate split that KI-002 describes.
  - `indicator_manager.py:76` and `:93-97` — replace both with `should_badge`.
- **Depends on:** None
- **Acceptance:** A dirty but unlinked layer enables nothing in any consumer.
  A linked dirty vector layer is treated consistently by menu, badge and
  prompt. Raster data sync stays reachable from the menu; rasters show no data
  badge and stay excluded from the close prompt. Dirty-state raster logic is
  confined to `layer_sync_state.py`; unrelated raster checks may remain. No import
  cycle.
- **Evidence:** New `test_layer_sync_state.py` parametrised over
  linked/unlinked × clean/dirty-data × clean/dirty-style × vector/raster,
  asserting the KI-007 effects table. Add a test asserting rasters report
  `UNKNOWN`, documenting the state until the raster evaluator in Tasks 11-15
  is implemented.
  Consumer-level
  tests go in the existing `test_close_sync_prompt.py` and
  `test_indicator_manager.py`; the menu needs a real view with a current
  group, so assert on the `QAction.isEnabled()` values produced by
  `on_context_menu`.

#### Task 8: Track all layers, filter at refresh time

- **Estimate:** ~130 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/layer_management/indicator_manager.py`,
  `tests/layer_management/test_indicator_manager.py`
- **Description:** Address KI-003.
  - `indicator_manager.py:60` — drop the registration-time
    `is_rana_linked(layer)` condition; keep the duplicate-id guard.
  - `indicator_manager.py:68-71` — widen the key filter from the two dirty
    keys to those plus `RanaLayerRef.PROPERTY_KEYS.values()`
    (`layer_manager.py:342-347`). Reference the constant; do not duplicate
    the string literals.
  - `indicator_manager.py:73-100` — `update_layer` and `update_group` call
    `should_badge` from Task 7, which applies the linking filter at refresh
    time.
  - `track_layers` must ensure an initial refresh after the layer-tree node
    exists. QGIS emits `layersAdded` before that node is available, so refresh
    tracked layers from the root's `addedChildren` notification. Otherwise an
    already-dirty linked layer would show no badge until something else
    changed.

  `set_rana_refs` writes four properties sequentially
  (`layer_manager.py:371-374`), so partial-reference notifications are
  expected. Recompute on each; the final write produces the correct badge. Do
  not add batching. Scope is unchanged: layers added while the plugin runs,
  **no** startup scan of pre-existing layers — that is deferred KI-008.
  `local_linking.py` needs no changes.
- **Depends on:** Task 7
- **Acceptance:** A layer linked *after* being added to the project gets a
  badge when dirty, and its ancestor groups recompute. Unlinking removes the
  badge even though the raw dirty properties remain. Removal of an
  **unlinked** tracked layer still disconnects cleanly. Teardown leaves no
  registered indicators or live connections.
- **Evidence:** The existing helper `make_linked_vector_layer`
  (`test_indicator_manager.py:12-16`) links before adding and so cannot
  exercise KI-003; add an unlinked-layer helper that links after
  `addMapLayer`. Cover link-after-add, unlink via `clear_rana_refs`, ancestor
  recomputation with mixed descendants, and disconnect cleanup for both
  linked and unlinked layers.

#### Task 9: Lock down the style/attach ordering (skipped)

- **Status:** Skipped at the engineer's request; the explicit comments and
  ordering tests were removed as too prescriptive. The current code order is
  unchanged.
- **Estimate:** ~35 lines (not implemented)
- **Files:** none
- **Description:** Originally proposed documenting and testing the ordering of
  `loadNamedStyle` before `attach_dirty_tracking` at
  `layer_manager.py:485-488`, `:549-552`. Engineer judged this level of
  explicitness unnecessary; do not re-add these changes without revisiting
  that decision.
- **Depends on:** None
- **Acceptance:** Skipped.
- **Evidence:** Skipped at the engineer's request.

#### Task 10: Confirm or diagnose KI-004 (done)

- **Estimate:** ~120 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/utils/qgis.py`,
  `rana_qgis_plugin/layer_management/layer_manager.py`,
  `rana_qgis_plugin/workers/style_layers.py`,
  `rana_qgis_plugin/workers/styling.py`,
  `tests/utils/test_qgis.py`, `tests/test_layer_manager.py`
- **Description:** KI-004 was reproduced by the engineer on 2026-10-21: sync a
  style, reopen the file, and the layer is style-dirty immediately. Root cause
  is a custom-property round-trip through the `.qml`, not a spurious
  `styleChanged` emitter — see KI-004 in the design.

  Fix: `strip_rana_properties_from_qml` removes every `rana/`-prefixed custom
  property from a QML file. Applied after `saveNamedStyle` on the upload paths
  and before `loadNamedStyle` on the open paths, so it both stops new
  pollution and repairs styles already stored on the server. Operating on the
  file rather than the layer keeps live layers untouched, which matters
  because the upload path snapshots layers that are still in the project.

  Rana references are now written **after** the style is applied, since
  `loadNamedStyle` replaces the whole custom-property block.
- **Depends on:** Tasks 7 and 8
- **Acceptance:** Reopening a file whose style was synced while dirty leaves
  both dirty flags unset and keeps the correct Rana references. No `rana/`
  property appears in an uploaded QML.
- **Evidence:** `tests/utils/test_qgis.py` covers the utility (removal,
  preservation of non-Rana properties, unparsable input).
  `tests/test_layer_manager.py` reproduces the reported bug through the real
  open path. Full suite: 460 passed, 2 skipped.

### Follow-up: raster data dirty detection

These tasks implement the "Raster data dirty detection" section of
`design.md`. The filesystem evaluator is enabled for eligible Rana-linked
rasters only; vectors continue using `afterCommitChanges`.

#### Task 11: Fingerprint the Rana raster source file

- **Estimate:** ~90 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/layer_management/file_fingerprint.py` (new),
  `tests/layer_management/test_file_fingerprint.py` (new)
- **Description:** Add a pure `fingerprint_file(path) -> str | None` helper
  returning a truncated `sha256` digest of the uploaded raster's filename,
  size, and `mtime_ns`. Do not fingerprint companion sidecars: data sync uploads
  only the main source file. Return `None` for a missing/unreadable source
  file. Add a helper that resolves a linked raster's source only when its
  provider is `gdal` and the source resolves beneath `rana_cache_dir()`.
- **Depends on:** None
- **Acceptance:** Identical source-file state yields an identical fingerprint;
  changing its size or mtime changes the fingerprint; missing/unreadable
  source files yield `None`; non-GDAL or out-of-cache sources are not
  evaluable. Sidecars aren't fingerprinted because they aren't uploaded as
  raster data.
- **Evidence:** Focused tests use `tmp_path`; path eligibility tests use the
  `qgis_application` fixture where QGIS layer objects are required.

#### Task 12: Add layer-scoped raster baseline evaluation

- **Estimate:** ~120 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/layer_management/raster_dirty_evaluator.py` (new),
  `rana_qgis_plugin/layer_management/layer_dirty_flags.py`,
  `rana_qgis_plugin/layer_management/layer_manager.py`,
  `tests/layer_management/test_raster_dirty_evaluator.py` (new)
- **Description:** Define `DATA_FINGERPRINT_PROPERTY =
  "rana/data_fingerprint"` and `DATA_SYNC_STATE_PROPERTY =
  "rana/data_sync_state"` alongside the existing style-state property.
  Implement explicit baseline capture and evaluation for an eligible linked
  raster: no baseline or ineligible source -> `UNKNOWN`; matching fingerprint
  -> `CLEAN`; mismatch -> `DIRTY`. Reflect evaluated state in
  `rana/data_sync_state` so existing consumers and property notifications remain
  the integration path. A missing/unreadable source file stores `unknown`. Do not capture
  a missing baseline merely because an existing layer/project was opened.
  Extend `clear_rana_refs` to remove the fingerprint along with the Rana
  identity properties.
- **Depends on:** Task 11
- **Acceptance:** Tests cover missing baseline, matching/mismatching content
  metadata, ineligible source, and unlinking. Unknown does not become clean
  or dirty; `clear_rana_refs` removes the fingerprint without changing the
  vector dirty-tracking behavior.
- **Evidence:** Focused evaluator and layer-manager tests pass using real QGIS
  layer objects where appropriate.

#### Task 13: Capture baselines after successful download and upload

- **Estimate:** ~100 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/loader.py`,
  `tests/loader/test_open.py`,
  `tests/loader/test_upload.py`
- **Description:** Identify the completion path that knows a Rana raster was
  successfully written, and capture its baseline only after the write has
  completed. Ensure a re-download updates the baseline for the corresponding
  linked raster layer(s), making the newly downloaded copy clean. Do not
  baseline arbitrary existing files during normal project/layer open. After a
  successful data upload, replace the baseline for affected raster layers
  instead of only setting data state clean; failed or cancelled uploads
  must retain the previous baseline and dirty state. Preserve style sync and
  vector dirty handling. Accept the documented local-edit-during-upload race
  in KI-009; do not add file locking or snapshotting in this task.
- **Depends on:** Task 12
- **Acceptance:** First successful download and re-download establish a
  baseline after file completion; re-downloading a modified raster results in
  `CLEAN`; successful data upload results in `CLEAN`; failed/cancelled upload
  does not clear dirty state or advance the baseline; opening an existing
  baselineless raster remains `UNKNOWN`.
- **Evidence:** Focused download and upload tests cover success, failure, and
  re-download; existing vector upload tests remain green.

#### Task 14: Watch raster files and revalidate project layers

- **Estimate:** ~170 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/layer_management/raster_watch.py` (new),
  `rana_qgis_plugin/rana_qgis_plugin.py`,
  `tests/layer_management/test_raster_watch.py` (new)
- **Description:** Add a lifecycle-managed watcher for eligible linked
  rasters. Maintain a `QFileSystemWatcher` for each raster's main source file,
  which is the file data sync uploads. Refresh its watch after change signals
  to handle atomic replacement at the same path. If that path is removed or
  renamed, stop tracking the layer; do not follow other files in its directory.
  Debounce notifications through a shared single-shot timer (~1.5 s) and
  evaluate affected layers only. Register for layers added and
  removed, and revalidate existing linked rasters when the watcher connects/
  project is read. This project-start scan must not create missing baselines.
  Wire watcher connect/disconnect alongside existing plugin managers and
  clean up watches and signal connections on layer removal and plugin unload.
- **Depends on:** Task 13
- **Acceptance:** An in-place write to the source file and atomic replacement
  at the same path are detected; removal/rename of the watched file stops
  tracking it; bursts coalesce;
  existing project layers are revalidated without receiving a new baseline; removing a
  layer or disconnecting removes its watches/connections.
- **Evidence:** Focused tests exercise watcher lifecycle and debounce with
  temporary files; avoid timing-sensitive assertions where signal dispatch
  can be driven directly.

#### Task 15: Integrate evaluated raster state with consumers

- **Estimate:** ~100 lines (implementation and tests)
- **Files:** `rana_qgis_plugin/layer_management/layer_sync_state.py`,
  `rana_qgis_plugin/layer_management/raster_dirty_evaluator.py`,
  `rana_qgis_plugin/layer_management/close_sync_prompt.py`,
  `tests/layer_management/test_layer_sync_state.py`,
  `tests/layer_management/test_close_sync_prompt.py`,
  `.minispec/specs/feat_470_file_sync/design.md`
- **Description:** Replace the hard-coded raster `UNKNOWN` result with the
  persisted `LayerSyncState` in `rana/data_sync_state`. Re-evaluate eligible
  rasters before dirty-file group collection for close/removal prompts, and
  remove the prompt's raster data exclusion. Keep context-menu and indicator
  refresh on the cached state property; neither path should walk the filesystem.
  Preserve the
  policy that `UNKNOWN` is syncable from the menu but does not badge or enter
  close/removal data-sync lists. Update KI-007 to describe the implemented
  detection and the remaining `UNKNOWN` cases.
- **Depends on:** Tasks 12 and 14
- **Acceptance:** A fingerprint mismatch badges and enters the close/removal
  data-sync list; a matching baseline does neither; an unknown raster remains
  menu-syncable but has no badge/prompt entry; raster state predicates read
  cached properties only; vector behavior is unchanged.
- **Evidence:** Dirty-state and close-prompt tests cover raster clean/dirty/
  unknown cases; full unit suite passes.

## Dependencies & Parallel Opportunities

- Task 1's Loader-signal approach is superseded; Task 2 removes that signal
  while implementing the layer-level indicator using property notifications.
- Tasks 2 and 4 touch separate code areas and can be implemented in parallel.
- Task 3 depends on Task 2's indicator-manager foundation.
- Task 5 depends on Task 4's dirty-group scan.
- Task 6 integrates the finished indicator manager and close-sync prompt, so
  it depends on Tasks 3 and 5.
- Task 8 depends on Task 7 for the shared `should_badge` predicate.
- Task 9 was skipped at the engineer's request.
- Task 10 confirmed KI-004 and fixed it; see the design.
- The style-fingerprint work (former Tasks 8-10) is deferred; see the scope
  decision at the top of this section. Raster file fingerprinting is a
  separate, accepted design and is covered by Tasks 11-15.
- Task 12 depends on Task 11; Task 13 depends on Task 12; Task 14 depends on
  Task 13; Task 15 depends on Tasks 12 and 14.
- No task adds E2E tests; those require separate explicit permission per the
  repository testing policy.

## Notes

- Dirty indicators rely on `QgsMapLayer.customPropertyChanged` for both dirty
  property additions and removals; no new Loader signal is needed.
- Schematisation dirty tracking remains out of scope.
- Raster fingerprints are stat-based and may conservatively report dirty
  after a byte-identical rewrite; contents are never read to compute them.
- A local raster edit during an upload can race with baseline capture at
  completion; see KI-009. This is accepted for now.
- Baselines are layer custom properties saved with the project. A missing
  baseline remains `UNKNOWN`; opening an existing raster never assumes that
  the current file matches Rana.
- The close warning cannot cancel project clearing. “Continue without
  syncing” is intentionally not labeled “Cancel.”
- `QgsMapLayer.styleChanged` is emitted imperatively by each QGIS editing
  widget, not automatically. Its behaviour cannot be inferred by mimicking a
  mutation in a test — only the caller decides. See KI-001.
- The dirty custom property is the single source of truth. The context menu
  and close prompt poll it; the badge subscribes to it. The badge must never
  become an input to the other two.

## Manual UI verification (Tasks 7-10)

- Colour-wheel edit on a linked vector layer: badge, menu and close prompt
  all react.
- Labeling change via the Layer Styling dock: verify whether it marks the
  layer dirty (KI-001 remains deferred; this is an observation, not a
  guaranteed fix).
- Open a Rana vector file with its usual sidecar `.qml`: nothing is dirty.
- Link a layer via local-linking after it is already in the project: badge
  appears when dirty.
- Sync via the context menu: badge clears and stays clear while panning and
  zooming.
- Raster without a baseline: "Save data to Rana" stays enabled, no data badge
  or close-prompt data entry.
- Remove a dirty group; close a project with dirty layers.

## Manual UI verification (Tasks 11-15)

- Open/download an untouched Rana raster: it has a baseline and no data badge.
- Replace or modify the linked main raster file outside QGIS: a data badge
  appears within a few seconds without reopening the project.
- Change or add a sidecar without changing the main raster: no data badge or
  close-prompt data entry appears.
- Sync raster data from the context menu: after successful upload, the badge
  clears and remains clear while the raster is unchanged.
- Modify the raster again and close/remove its layer: it appears in the data
  section of the prompt.
- Re-download the raster while it is locally dirty: after download completes,
  its baseline is replaced and the badge clears.
- Reopen a project with a stored baseline: state is revalidated against disk;
  reopen a legacy project with no baseline: state remains `UNKNOWN` rather
  than being assumed clean.
- Add a non-file-backed raster: it remains `UNKNOWN`, with no badge/prompt
  entry while the context-menu data action remains available.

## Progress

- [x] Task 1: Add Loader sync-completion notification (superseded)
- [x] Task 2: Use native property notifications for layer-level indicators
- [x] Task 3: Aggregate indicators and keep their lifecycle current
- [x] Task 4: Collect dirty file groups for close-time sync
- [x] Task 5: Prompt and dispatch sync before project clearing
- [x] Task 6: Wire managers into plugin lifecycle and verify the feature
- [x] Task 7: Define one shared dirty state
- [x] Task 8: Track all layers, filter at refresh time
- [x] Task 9: Lock down the style/attach ordering (skipped at engineer request)
- [x] Task 10: Confirm or diagnose KI-004
- [x] Task 11: Fingerprint the Rana raster source file
- [x] Task 12: Add layer-scoped raster baseline evaluation
- [x] Task 13: Capture baselines after successful download and upload
- [x] Task 14: Watch raster files and revalidate project layers
- [x] Task 15: Integrate evaluated raster state with consumers
