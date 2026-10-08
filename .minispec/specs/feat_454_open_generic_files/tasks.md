---
feature: feat_454_open_generic_files
status: complete
created: 2026-08-18
chunk_size: adaptive
total_tasks: 23
estimated_lines: ~1170
---

# Open Rana Files/Layers in QGIS — Tasks

## Overview

Implements the three-phase design: open files/layers into the layer panel,
save style/data back to Rana, and keep layer-panel references in sync with
Rana state changes.

## Task List

### Foundation

#### Task 1: `rana_open_cache_dir()` setting
- **Estimate:** ~15 lines
- **Files:** `rana_qgis_plugin/utils/settings.py`
- **Description:** Add `rana_open_cache_dir()` getter and `set_rana_open_cache_dir()` setter, defaulting to `Path(tempfile.gettempdir()) / "rana_downloads"`. Mirrors the existing `rana_cache_dir()` pattern.
- **Depends on:** None
- **Acceptance:** Setting can be read/written via QgsSettings.
- **Evidence:** Unit test passes (get/set round-trip, default value).
- **Manual test:** N/A (infrastructure only).

#### Task 2: `utils/rana_layer_refs.py` — reference data helpers
- **Estimate:** ~50 lines + ~40 lines tests
- **Files:** `rana_qgis_plugin/utils/rana_layer_refs.py` (new), unit test
- **Description:** `RanaLayerRef` dataclass with fields `project_id`, `file_path`, `descriptor_id`, `layer_id`. Functions: `set_rana_refs(layer, ...)`, `get_rana_refs(layer) -> RanaLayerRef | None`, `is_rana_linked(layer) -> bool`. All backed by `QgsMapLayer.setCustomProperty()` under `rana/` namespace. Include `clear_rana_refs(layer)` for Phase 3.
- **Depends on:** None
- **Acceptance:** Refs survive set/get round-trip on a QgsVectorLayer; `is_rana_linked` returns False for unlinked layers.
- **Evidence:** Unit tests pass.
- **Manual test:** N/A (infrastructure only).

#### Task 3: Confirm unified cache paths and atomic download contract
- **Estimate:** ~30 lines + ~20 lines tests
- **Files:** `rana_qgis_plugin/workers/download.py`, `rana_qgis_plugin/utils/local_paths.py`, `rana_qgis_plugin/workers/download_task.py` (new), unit tests
- **Description:** Use the renamed `rana_cache_dir()` as the single storage location for opened/downloaded files; do not add a `base_dir` parameter or a second open-cache context. Keep `FileDownloadContext` and the existing local-path helpers using `rana_cache_dir()`. Define the safe download-path contract for Task 4: each download writes to a sibling `.part` path and only atomically renames it to the final path after download and post-processing succeed; failed or canceled work removes the `.part` file. Do not add checksum validation. Deduplication within one multi-download request happens during preprocessing; concurrent tasks use a per-target lock, not a global `_in_flight` job set.
- **Depends on:** Task 1
- **Acceptance:** Existing `FileDownloadContext` resolves under `rana_cache_dir()` without API changes. Tests cover the unified path behavior and the `.part`/atomic-finalization contract; no `base_dir`, `rana_open_cache_dir`, or `_in_flight` mechanism remains in the new download flow.
- **Evidence:** Unit tests pass.
- **Manual test:** N/A.

#### Task 4: `DownloadTask(QgsTask)`
- **Estimate:** ~80 lines + ~30 lines tests
- **Files:** `rana_qgis_plugin/workers/download.py`, unit test
- **Description:** Replaces `SingleFileDownloadWorker` and `BatchFileDownloadWorker` (QThread-based). Accepts a list of `(downloader, download_context)` pairs. Runs sequentially, checks `isCanceled()` between files, emits `file_started(str)` and `file_failed(str, str)` signals, sets progress. Mirrors `UploadTask` pattern. Deduplicate jobs during batch preprocessing and coordinate concurrent tasks with a per-target lock keyed by the canonical file reference. Downloads MUST use a sibling `.part` path and atomically rename it to the final path only after download and post-processing succeed; remove incomplete `.part` files on failure/cancellation. Do not add checksum validation in this task.
- **Depends on:** Task 3
- **Acceptance:** Task downloads files to correct paths; cancellation stops processing; duplicate jobs in one batch are removed and duplicate concurrent launches are rejected; an interrupted or failed download leaves no final file and does not cause a later open to treat a `.part` file as complete.
- **Evidence:** Unit tests pass (mock downloader); `mypy` passes on new file.
- **Manual test:** N/A (tested via Task 6).

### Core Implementation — Phase 1

#### Task 5: Layer-tree group builder
- **Estimate:** ~80 lines + ~30 lines tests
- **Files:** `rana_qgis_plugin/layer_manager.py` (new function, legacy classes untouched)
- **Description:** New standalone function (e.g. `open_layer_in_project`) that accepts `parents: list[str]` (display-name path segments like `["Project A", "files", "foo", "bar.gpkg"]`) and a `RanaLayerRef` plus the local file path, layer name (for vectors), and data type. Does a find-or-create walk over `QgsLayerTreeGroup` per path segment, with group identity based on Rana reference metadata (custom property `rana/project_id` + `rana/path_segment`), not display name alone. Creates `QgsVectorLayer` (ogr, `path|layername=...` URI) or `QgsRasterLayer` and applies the `RanaLayerRef` via Task 2's helpers. The legacy `LayerManager`, `FileLayerManager`, and `PublicationLayerManager` classes remain untouched as reference.
- **Depends on:** Tasks 2, 3
- **Acceptance:** Opening a file creates correct group hierarchy; repeat open reuses groups; layers have rana refs set.
- **Evidence:** Unit tests pass (group creation, reuse, layer URI correctness).
- **Manual test:** Open a vector file via Task 6 → verify layer tree shows `Project / files / folder / file / layer` structure. Open same file again → no duplicates.

#### Task 6a: `handleDoubleClick` with download and open
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/data_items/file_item.py`, `rana_qgis_plugin/data_items/layer_item.py`
- **Description:** Implement `handleDoubleClick()` on `RanaFileDataItem` (downloads file via `DownloadTask`, then opens all layers) and `RanaLayerDataItem` (downloads parent file, opens single layer). The handler derives `parents` from `[project["name"], "files"] + file_item["id"].split("/")` and constructs a `RanaLayerRef` from the data item's attributes. Creates `FileDownloadContext` + `RanaFileDownloader`, submits a `DownloadTask`, and on completion calls `open_rana_vector_layers` / `open_rana_vector_layer` / `open_rana_raster` from the layer manager module.
- **Depends on:** Tasks 4, 5
- **Acceptance:** Double-clicking a Rana file/layer in the Browser downloads the file and opens it into the layer panel with correct group structure and refs.
- **Evidence:** Manual test; existing unit tests still pass.
- **Manual test:** Double-click a Rana vector file → layers appear grouped correctly. Double-click a raster → raster layer appears. Double-click an individual layer → only that layer opens.

#### Task 6b: Download progress bar
- **Estimate:** ~20 lines
- **Files:** `rana_qgis_plugin/loader.py`
- **Description:** Show a progress bar during file download, similar to how upload shows progress. Use the `DownloadTask` progress signal and `file_started`/`file_failed` signals to drive the message bar progress indicator. For single files, show determinate progress if content-length is available; for batches, show per-file progress (e.g. "Downloading file 2/5").
- **Depends on:** Task 6a
- **Acceptance:** Downloading a file shows a progress bar in the QGIS message bar. Progress clears on completion or shows error on failure.
- **Evidence:** Manual test.
- **Manual test:** Double-click a large raster file → progress bar visible during download → clears when layer appears.

#### Task 6c: Context-menu action, multi-select, folder traversal, and batch de-duplication
- **Estimate:** ~80 lines
- **Files:** `rana_qgis_plugin/data_items/file_item.py`, `rana_qgis_plugin/data_items/layer_item.py`, `rana_qgis_plugin/data_items/gui_provider.py`
- **Description:** Connect the existing `FileAction.OPEN_IN_QGIS` QAction to the same open code path used by `handleDoubleClick`. Add `OPEN_IN_QGIS` to the multi-select action whitelist in `gui_provider.py` and extend valid multi-selection classification to include `RanaLayerDataItem`. The action handler receives the complete valid Browser selection and resolves it into one de-duplicated batch of openable files/layers. When the selection contains folders (or the aggregate file count exceeds 10 or nested folders are present), recursively traverse to resolve all openable files, de-duplicate, and show one confirmation dialog with the aggregate count. On confirm, submit one batch `DownloadTask`; cancellation prevents the entire batch. Overlapping selected folders do not duplicate downloads or layer-tree entries. Individual layers open without folder traversal. This also covers the folder-level "Open in QGIS" (Task 7 reuses this logic).
- **Depends on:** Task 6a
- **Acceptance:** Right-click file/layer → "Open in QGIS" works. Ctrl-click multiple files/layers → "Open in QGIS" opens all. Selection with folders triggers traversal + confirmation. Overlapping folders don't duplicate. Cancel prevents all downloads.
- **Evidence:** Unit tests in `test_gui_provider.py` updated; manual test.
- **Manual test:** Right-click a raster → "Open in QGIS" → opens. Ctrl-click two files → both open. Select folder with many files → confirmation dialog. Select overlapping folders → one confirmation, no duplicates.

#### Task 6d: Folder-level "Open in QGIS"
- **Estimate:** ~50 lines
- **Files:** `rana_qgis_plugin/data_items/folder_item.py`
- **Description:** Add `OPEN_IN_QGIS` action to `RanaFolderDataItem.actions()`. Use the shared selection resolver from Task 6: recursively resolve all openable files (vector/raster) under the folder at any depth, aggregate multiple selected folders/files, remove duplicates, and preserve each item's Rana path metadata. If the aggregate contains nested folders or more than 10 resolved files, show one confirmation dialog with the aggregate recursive file count. On confirm, submit one batch `DownloadTask`; cancellation must prevent the entire batch. Do not implement per-folder action firing as the multi-select behavior—the GUI provider's whitelisted action must dispatch the complete selection once.
- **Depends on:** Task 6
- **Acceptance:** Right-clicking a folder with 3 vector files opens all without prompt. A folder with 15 files shows confirmation dialog first. Multiple selected folders/files, including overlapping folders, use one aggregate confirmation and one de-duplicated batch; unsupported selections cannot bypass the existing multi-select safety gates.
- **Evidence:** Manual test (below).
- **Manual test:** Right-click a Rana folder containing a few files → "Open in QGIS" → all open. Try a folder with many files → confirmation dialog appears with correct count. Repeat with multiple and overlapping folders, mixed file/folder selections, and cancel/confirm paths.

#### Task 8: Security audit of style-zip extraction
- **Estimate:** ~30 lines (fixes)
- **Files:** `rana_qgis_plugin/workers/download.py`
- **Description:** Audit the zip extraction in `RanaFileDownloader` (style zip handling) for path-traversal (zip-slip) vulnerabilities. Add validation that extracted paths stay within the target directory. Fix any issues found.
- **Depends on:** None (can run in parallel with anything)
- **Acceptance:** Malicious zip entries with `../` paths are rejected or sanitized.
- **Evidence:** Unit test with a crafted zip containing path-traversal entries → extraction rejects them.
- **Manual test:** N/A.

### Core Implementation — Phase 2

#### Task 9: Central sync lock registry + layer management module
- **Estimate:** ~50 lines + ~20 lines tests
- **Files:** `rana_qgis_plugin/layer_management/__init__.py` (new package), `rana_qgis_plugin/layer_management/sync_lock.py` (new)
- **Description:** New `layer_management` package (or similar — discuss naming). Contains a sync lock registry: module-level dict keyed by `(project_id, descriptor_id)`. API: `acquire_sync_lock(key) -> bool`, `release_sync_lock(key)`, `is_sync_locked(key) -> bool`. Prevents concurrent save operations targeting the same underlying Rana file from any layer/group. Consider whether `layer_manager.py` should move into this package (flag for later, don't do it in this task).
- **Depends on:** None
- **Acceptance:** acquire/release works; second acquire on same key returns False; release allows re-acquire.
- **Evidence:** Unit tests pass.
- **Manual test:** N/A (infrastructure only).

#### Task 10: Layer-tree context menu provider
- **Estimate:** ~80 lines
- **Files:** `rana_qgis_plugin/layer_management/layer_tree_menu.py` (new)
- **Description:** Implement `QgsLayerTreeViewMenuProvider` (or hook `iface.layerTreeView().contextMenuAboutToShow`). Adds "Save style to Rana" and "Save data to Rana" entries for layers/groups where `is_rana_linked()` is True. "Save data" is hidden/disabled on individual layers inside multi-layer vector files (only shown at file/group level). Both actions disabled when `is_sync_locked()` for the layer's canonical key. Register provider in plugin init.
- **Depends on:** Tasks 2, 9
- **Acceptance:** Right-clicking a rana-linked layer shows "Save style to Rana". Right-clicking a file-level group shows both. Individual layer in multi-layer file does NOT show "Save data". Actions disabled during sync.
- **Evidence:** Manual test (below).
- **Manual test:** Open a rana vector file (Phase 1). Right-click the layer in layer panel → "Save style to Rana" visible. Right-click file-level group → both actions visible. (Actions won't work yet until Task 11/12.)

#### Task 11a: `SyncDataTask(QgsTask)` — upload existing file data
- **Estimate:** ~70 lines + ~25 lines tests
- **Files:** `rana_qgis_plugin/workers/sync_task.py` (or a dedicated data-sync module), `rana_qgis_plugin/utils/upload.py`
- **Description:** Implement a data-only `QgsTask` for replacing an existing Rana file. Reuse `utils/upload.py`'s existing-file upload utilities and upload API flow (`start_file_upload`/`finish_file_upload`) rather than duplicating upload handling. The task receives the local file and canonical Rana reference, honors cancellation/progress, acquires the central sync lock, releases it on completion, and emits the existing loader refresh signal for the affected folder. No style-building or style-specific polling belongs in this task.
- **Depends on:** Tasks 9, 10
- **Acceptance:** Existing local file data is uploaded through shared upload utilities; cancellation and failures are handled; lock and refresh behavior are correct; dirty data state is cleared only after success.
- **Evidence:** Unit tests pass (focused API/test doubles).
- **Manual test:** Open a Rana-linked vector file, edit and commit changes, choose "Save data to Rana", then verify the updated file is visible after Browser refresh.

#### Task 11b: `SyncStyleTask(QgsTask)` — upload multiple generated styles
- **Estimate:** ~100 lines + ~30 lines tests
- **Files:** `rana_qgis_plugin/workers/styling.py`, `rana_qgis_plugin/workers/sync_task.py` (or a dedicated style-sync module)
- **Description:** Rewrite the styling worker as a `QgsTask` and extend it to accept multiple style files/layers in one operation. Generate/validate QML files using the existing style builders, upload the batch through the existing styling API infrastructure, preserve descriptor-processing polling/retry behavior, honor cancellation/progress, acquire the central sync lock, release it on completion, and emit completion/failure signals. Keep style sync separate from data-upload utilities. Remove the temporary mypy exemption after the rewrite.
- **Depends on:** Tasks 9, 10
- **Acceptance:** One task can sync one or many styles; generation, upload, polling, cancellation, progress, locking, and dirty-style clearing work; failures do not clear dirty state.
- **Evidence:** Unit tests pass (single/multi-style, cancellation, polling/failure paths).
- **Manual test:** Change styles on one or multiple Rana-linked layers, choose "Save style to Rana", then verify all styles appear in Rana and repeat activation is disabled while syncing.

#### Task 11c: Sync lock and dirty-state completion integration
- **Estimate:** ~60 lines + ~30 lines tests
- **Files:** integration touches `rana_qgis_plugin/layer_management/sync_lock.py`, `rana_qgis_plugin/workers/sync_task.py`, `rana_qgis_plugin/workers/styling.py`, and the upload/task orchestration points
- **Description:** Connect the existing `LayerLockRegistry`/central sync lock to the actual upload orchestration for both data and style uploads. Before queueing or starting a `FileUploadTask` or `StyleUploadTask` acquire the canonical lock keyed by `(project_id, descriptor_id|file_id)`. If acquire fails because the key is already locked, reject/skip the request (surface a user-facing warning or no-op); do not allow concurrent uploads targeting the same Rana file/descriptor. Ensure the lock is released on success, failure, or cancellation (all lifecycle exits).

- On successful data sync: clear `rana/data_dirty` for all affected linked layers. On successful style sync: clear `rana/style_dirty` for affected layers. Preserve dirty flags on failure or cancellation.

- Keep the layer-tree menu gating (Task 10) as a UI guard but treat task orchestration as the enforcement point — menu disabling is not the sole protection against concurrent writes.

- Add focused unit tests: lock lifecycle (acquire/reject/release across success, failure, cancellation), successful-clearing behavior (data and style), and failed/cancelled tasks preserving dirty flags.
- **Depends on:** Tasks 9, 11a, 11b (and requires the dirty-flag helpers defined in Task 12 to be available for the clear/inspect operations; coordinate ordering if necessary)
- **Acceptance:** Concurrent sync attempts for the same Rana canonical key are prevented; locks release on all exits; successful uploads clear the respective dirty flags; failed/cancelled uploads leave dirty flags intact. Unit tests exercising lock lifecycle and flag clearing/preservation pass.
- **Evidence:** Unit tests pass; manual test described below.
- **Manual test:** Trigger two concurrent "Save data to Rana" for the same file — the second attempt is rejected/short-circuited. Perform a successful data upload → `rana/data_dirty` cleared on linked layers. Simulate upload failure/cancellation → `rana/data_dirty` remains set.

#### Task 11d: Rename and move file upload task/module
- **Estimate:** ~20 lines
- **Files:** `rana_qgis_plugin/utils/upload.py` -> `rana_qgis_plugin/workers/upload.py`, any modules importing `UploadTask`/utilities, and related tests
- **Description:** Move the existing upload utilities from `rana_qgis_plugin/utils/upload.py` into `rana_qgis_plugin/workers/upload.py`. Rename `UploadTask` to `FileUploadTask` (class name only) to clearly distinguish it from `DownloadTask` and `StyleUploadTask`. Update all imports, type annotations, and tests to reference the new module path and class name. Do not change runtime behavior or public API beyond the module/class rename.
- **Clarification:** This change separates concerns: `DownloadTask`, `FileUploadTask`, and `StyleUploadTask` should be distinct types and live under `workers/`.
- **Tests:** Focused regression/import tests to ensure no import breakage; update any type-annotation references in tests.
- **Depends on:** Tasks 4, 11a
- **Acceptance:** The module is moved and renamed with imports updated; mypy/pytest run without import errors; behavior unchanged.
- **Evidence:** Minimal import/regression unit tests pass; CI/mypy not broken.
- **Manual test:** Run unit tests; confirm no runtime import errors when instantiating `FileUploadTask` and existing upload flows still work.

#### Task 12: Dirty-state tracking
- **Estimate:** ~50 lines
- **Files:** `rana_qgis_plugin/layer_management/dirty_tracking.py` (new) or extend `layer_manager.py`
- **Description:** When a rana-linked layer is added to the project (Task 5 group builder calls this), connect: `afterCommitChanges` → set `rana/data_dirty` custom property (vector only); `styleChanged` → set `rana/style_dirty` (any layer type). Flags are idempotent. Cleared only by SyncTask on success. Raster layers: no data-dirty tracking, "Save data" always enabled. Surface dirty state visually (e.g. layer name decoration or icon badge — implementation detail).
 - **Description:** When a rana-linked layer is added to the project (Task 5 group builder calls this), connect: `afterCommitChanges` → set `rana/data_dirty` custom property (vector only); `styleChanged` → set `rana/style_dirty` (any layer type). Flags are idempotent. Cleared only by SyncTask on success. Raster layers: no data-dirty tracking, "Save data" always enabled. Surface dirty state visually (e.g. layer name decoration or icon badge — implementation detail). Note: visual dirty-state decoration (name decoration / QgsLayerTreeViewIndicator badge) is being deferred for now. Instead, dirty state is surfaced by gating the "Save style/data to Rana" layer-tree menu actions — those actions are enabled only when the corresponding `rana/style_dirty` or `rana/data_dirty` flag is set. A visual indicator can be added later if UX testing indicates it's needed.
- **Depends on:** Task 5 (signal connections), Task 11c (flag clearing)
- **Acceptance:** Edit a vector layer and commit → `rana/data_dirty` is True. Change style → `rana/style_dirty` is True. After successful sync → flags cleared.
- **Evidence:** Unit tests (signal → flag set); manual test below.
- **Manual test:** Open a rana vector file, toggle editing, make an edit, save edits → dirty indicator appears. Save style to Rana → indicator clears.

### Core Implementation — Phase 3

#### Task 13: Loader `item_renamed`/`item_deleted` signals
- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/loader.py`
- **Description:** Add `item_renamed = pyqtSignal(str, str, bool)` (old_path, new_path, is_folder) and `item_deleted = pyqtSignal(str, bool)` (path, is_folder) signals to `Loader`. Emit from existing `rename_item()`, `delete_file()`, `delete_folder()` methods on success.
- **Depends on:** None (can run in parallel with Phase 2 tasks)
- **Acceptance:** Renaming/deleting a file via the Browser emits the corresponding signal.
- **Evidence:** Unit test (mock Loader, trigger rename → signal emitted with correct args).
- **Manual test:** N/A (tested via Task 14).

#### Task 14: Local-session linking listener
- **Estimate:** ~50 lines + ~20 lines tests
- **Files:** `rana_qgis_plugin/layer_management/local_linking.py` (new)
- **Description:** Subscribe to `Loader.item_renamed` and `Loader.item_deleted`. On rename: iterate all rana-linked layers, remap `file_path` where it starts with `old_path` (prefix-based). Display names and group names are NEVER changed. On delete: call `clear_rana_refs()` on affected layers (disables sync actions). Layer itself is never removed.
- **Depends on:** Tasks 2, 13
- **Acceptance:** Rename a file in Browser → layer's stored ref path updates. Delete a file → layer's rana refs cleared, sync actions disabled.
- **Evidence:** Unit tests pass; manual test below.
- **Manual test:** Open a rana file, then rename it via Browser right-click → layer still works, "Save style to Rana" still available. Delete the file via Browser → "Save style/data to Rana" disappears from context menu.

#### Task 15: Remote-change lazy guard (pre-save check)
- **Estimate:** ~60 lines + ~20 lines tests
- **Files:** `rana_qgis_plugin/loader.py`, API status plumbing as needed
- **Description:** Immediately before `StyleUploadTask` or `FileUploadTask` is queued, run a verification check. Style-save: `GET /tenants/{tenant}/file-descriptors/{descriptor_id}`. Data-save: `GET .../files/stat?path=<file_path>`. Error taxonomy: HTTP 404/410 → clear refs, disable actions, warn user, abort permanently for that stored reference (no retry). Network/timeout/5xx/auth errors → preserve refs, warn "could not verify — try again", abort this attempt only; the user may retry the save later. If API error-response distinction is unclear during implementation, flag as risk and document the assumption.
- **Depends on:** Task 11
- **Acceptance:** Save attempt on a deleted remote file → refs cleared, warning shown. Save attempt during network outage → refs preserved, warning shown, action remains available after retry.
- **Evidence:** Unit tests (mock 404 → refs cleared; mock 503 → refs preserved).
- **Manual test:** Delete a file via Rana web UI, then try "Save style to Rana" in QGIS → warning appears, action disabled. Disconnect network, try save → warning about verification failure, action remains available after reconnecting.

#### Task 15a: Offer recovery after definitive remote deletion
- **Estimate:** TBD
- **Files:** To be determined during task breakdown
- **Description:** Design and implement an explicit recovery flow for a confirmed 404/410 during data save. Preserve the local layer and its dirty state, offer to re-upload the local data file as a new Rana resource, define destination-folder and conflict behavior, and update or replace stored Rana references only after a successful upload. Style saves only clear stale references and do not offer re-upload, because the style endpoint targets a descriptor associated with the missing file. Do not retry the failed save automatically and do not offer recovery for transient verification failures. Deferred until the future automatic-sync design is settled.
- **Depends on:** Task 15
- **Acceptance:** A definitively missing remote file can be intentionally re-uploaded through a user-confirmed flow; canceling preserves the local layer and dirty state; transient verification failures do not offer re-upload.
- **Evidence:** Design review and focused unit tests; manual verification of confirm/cancel/conflict paths.
- **Manual test:** Delete a data file remotely, attempt "Save data to Rana", choose re-upload, and verify the local file is restored in Rana with valid updated references. Delete a file remotely, attempt "Save style to Rana", and verify no re-upload is offered.

#### Task 16: Warn before quitting with unsynced Rana files
- **Estimate:** ~30 lines + ~20 lines tests
- **Files:** `rana_qgis_plugin/layer_management/dirty_tracking.py`, `rana_qgis_plugin/rana_qgis_plugin.py`
- **Description:** Add `get_dirty_rana_layers()` to identify Rana-linked layers with `rana/data_dirty` or `rana/style_dirty`. Extend the existing main-window event filter to handle only the QGIS application close event. If dirty Rana layers exist, show a simple warning listing the affected filenames and offer `Cancel` or `Quit anyway`. Cancel must call `event.ignore()` and prevent QGIS from quitting. Quit anyway leaves all state unchanged and allows normal shutdown. Do not hook `QgsProject.aboutToBeCleared`, New Project, Open Project, project save, or sync orchestration in this task. Local edits and QGIS's native project-save flow remain unchanged.
- **Depends on:** Task 12
- **Acceptance:** Quitting with dirty Rana layers shows the affected filenames; Cancel prevents quitting; Quit anyway proceeds. Quitting without dirty Rana layers is unchanged. New/Open/Close Project behavior is unchanged.
- **Evidence:** Unit tests cover dirty-layer discovery; manual testing covers the close-event warning and cancel/continue behavior.
- **Manual test:** Open a Rana file, change data or style without syncing, quit QGIS, verify the warning lists the filename, Cancel keeps QGIS open, and Quit anyway exits. Repeat with no dirty Rana layers and verify no extra warning.

### Cleanup

### Follow-up correctness tasks

#### Task 21: Make local reference updates project-scoped
- **Description:** Include project identity in rename/delete handling and update
  or clear only linked layers belonging to that project. Paths alone can collide
  across projects.
- **Depends on:** Task 14
- **Acceptance:** Same paths in different projects are never cross-updated.
- **Evidence:** Unit tests for identical paths across two projects.
- **Status:** Complete.

#### Task 22: Move batch preparation behind confirmation
- **Status:** Deferred technical debt. The current implementation is working
  acceptably and no user-facing blocking problem has been observed. Revisit if
  URL resolution becomes slow or batch preparation starts causing UI freezes.
- **Description:** If revisited, count and classify the selection before
  resolving download URLs, and consider asynchronous preparation so the
  confirmation and preparation do not block the QGIS UI. The confirmation
  count must reflect successfully prepared files rather than failed requests.
- **Depends on:** Tasks 6c and 6d
- **Acceptance:** Deferred; no implementation required for this feature.
- **Evidence:** Revisit after a reproducible performance problem.
- **Status:** Pending.

#### Task 23: Separate download post-processing from API access
- **Status:** Deferred technical debt. Current downloads and post-processing
  work reliably in the supported environment, and no thread-related runtime
  problem has been observed.
- **Description:** If revisited, assess whether API access from task threads
  should be moved to a dedicated, event-loop-backed network thread. Preserve
  QGIS authentication and avoid duplicating authentication logic.
- **Depends on:** Task 4
- **Acceptance:** Deferred; no implementation required for this feature.
- **Evidence:** Revisit if hangs, crashes, thread warnings, or unreliable
  request completion are observed.
- **Status:** Pending.

#### Task 24: Make automatic style synchronization layer-scoped
- **Status:** Deferred until automatic style synchronization is implemented.
- **Description:** When automatic dirty-style uploads are introduced, export
  only the changed linked layer rather than rebuilding styles for the whole
  file/group. Keep the implementation aligned with the observed runtime
  behavior and measure whether main-thread export becomes a performance issue.
- **Depends on:** Tasks 11b and 12
- **Acceptance:** Deferred until automatic synchronization work starts.
- **Evidence:** Unit tests for selection, payload, and dirty-state handling when
  implemented.
- **Status:** Pending.

#### Task 25: Add ZIP extraction resource limits (deferred)
- **Description:** Path-traversal protection is already implemented. Defer
  member-count and compressed/uncompressed-size limits to a future hardening
  task; no implementation is required for this feature.
- **Depends on:** Task 8
- **Acceptance:** Deferred.

#### Task 17: Remove mypy exemptions for adapted files
- **Estimate:** ~5 lines
- **Files:** `mypy.ini`
- **Description:** As `workers/download.py`, `workers/styling.py`, and `layer_manager.py` are adapted in the tasks above, remove their corresponding `ignore_errors = True` entries from `mypy.ini`. Done incrementally: remove `download` exemption after Task 4, `layer_manager` after Task 5, `styling` after Task 11. This task tracks the obligation; actual removal happens within those tasks' definition-of-done.
- **Depends on:** Tasks 4, 5, 11
- **Acceptance:** `mypy.ini` has no `ignore_errors` entries for these three modules.
- **Evidence:** `mypy` runs clean on all three modules.
- **Manual test:** N/A.

### End-to-end verification

#### Task 18: Add fixtures and e2e support for layer sync
- **Estimate:** ~40 lines plus a small raster fixture
- **Files:** `e2e/data/upload.tif` (new), `e2e/test_layer_sync.py` (new),
  `e2e/test_utils.py` and/or e2e API helpers as needed
- **Description:** Add a minimal checked-in raster fixture alongside the existing
  vector fixture. Add only the shared helpers needed to create a project, upload
  both files into one folder, locate layer-tree nodes, wait for QGIS tasks, and
  query the real Rana API for post-upload verification. Test setup and teardown
  may use API helpers for speed; user-facing open and save operations must use
  the Browser/layer-panel UI.
- **Depends on:** Tasks 6d, 11c, 15
- **Acceptance:** The fixture can be uploaded as a valid raster file and the
  e2e module can reliably wait for layer opening and sync-task completion.
- **Evidence:** Fixture/API smoke checks pass in the e2e environment.
- **Manual test:** N/A.

#### Task 19: E2E opening flows
- **Estimate:** ~100 lines
- **Files:** `e2e/test_layer_sync.py`
- **Description:** Add one long opening-flow test. Create a folder containing
  the vector and raster fixtures, use the folder's "Open in QGIS" action, and
  verify the vector layer(s) and raster layer appear in the layer panel under
  the expected Rana group hierarchy. Repeat the folder action and verify groups
  and layers are not duplicated. Finally open one individual vector layer from
  the Browser and verify that the requested layer opens without opening its
  siblings.
- **Depends on:** Task 18
- **Acceptance:** Vector-file, raster-file, folder traversal, repeat-open
  deduplication, and individual-vector-layer paths work through the QGIS UI.
- **Evidence:** E2E test passes against the real Rana backend.
- **Manual test:** Open a folder containing vector and raster files; verify the
  layer tree and repeat-open behavior.

#### Task 20: E2E data/style sync and reference lifecycle
- **Estimate:** ~180 lines
- **Files:** `e2e/test_layer_sync.py`
- **Description:** Add one long sync-lifecycle test using a linked vector file.
  Modify and commit vector data, verify the layer-panel "Save data to Rana"
  action becomes available, trigger it through the UI, wait for completion, and
  verify the changed data through the real Rana API. Modify the layer style,
  verify "Save style to Rana" becomes available, trigger it through the UI,
  wait for completion, and verify the uploaded style through the real API.
  Then rename the file through the Browser and verify the linked layer retains
  its sync action/reference. Delete it through the Browser and verify the layer
  remains but Rana sync actions disappear. Finally use two additional linked
  files: delete one remote resource directly through the API and attempt a data
  save; delete the other and attempt a style save. Verify each lazy guard warns,
  clears the reference, and prevents the upload.
- **Depends on:** Task 18
- **Acceptance:** Data and style edits reach Rana through the UI-triggered sync
  tasks; both local rename/delete linking paths work; both data-save and
  style-save remote-deletion guards work against the real API.
- **Evidence:** E2E test passes against the real Rana backend.
- **Manual test:** Edit data and style, save each from the layer panel, rename
  and delete through the Browser, and simulate remote deletion before saving.

## Notes

- `utils/upload.py` should eventually move to `workers/` for consistency, but not part of this feature — track separately.
- The `layer_management/` package is new; if naming feels wrong during implementation, rename before merging Phase 2.
- Multi-select is provided by the existing `gui_provider.py` classification/intersection logic. `OPEN_IN_QGIS` must be explicitly whitelisted, and valid selections include files, folders, and individual layers. The action must dispatch the complete selection once; do not rely on QGIS firing the action independently per selected item.
- Visual treatment of dirty-state indicator is an implementation detail decided in Task 12.

## Progress

- [x] Task 1: `rana_open_cache_dir()` setting
- [x] Task 2: `utils/rana_layer_refs.py` — reference data helpers
- [x] Task 3: Adapt `FileDownloadContext` for open-cache base dir
- [x] Task 4: `DownloadTask(QgsTask)`
- [x] Task 5: Layer-tree group builder
- [x] Task 6a: `handleDoubleClick` with download and open
- [x] Task 6b: Download progress bar
- [x] Task 6c: Context-menu action, multi-select, folder traversal, batch de-duplication
- [x] Task 6d: Folder-level "Open in QGIS"
- [x] Task 8: Security audit of style-zip extraction
- [x] Task 9: Central sync lock registry + layer management module
- [x] Task 10: Layer-tree context menu provider
- [x] Task 11a: `SyncDataTask(QgsTask)` — upload existing file data
- [x] Task 11b: `SyncStyleTask(QgsTask)` — upload multiple generated styles
- [x] Task 11c: Sync lock and dirty-state completion integration
- [x] Task 11d: Rename and move file upload task/module
- [x] Task 12: Dirty-state tracking
- [x] Task 13: Loader `item_renamed`/`item_deleted` signals
- [x] Task 14: Local-session linking listener
- [x] Task 15: Remote-change lazy guard (pre-save check)
- [-] Task 15a: Offer recovery after definitive remote deletion (skipped)
- [-] Task 16: Warn before quitting with unsynced Rana files (skipped; superseded by future autosync)
- [x] Task 17: Remove mypy exemptions for adapted files (layer_manager; download deferred until port)
- [x] Task 18: Add fixtures and e2e support for layer sync (fixture/helper scaffold)
- [x] Task 19: E2E opening flows
- [x] Task 20: E2E data/style sync and reference lifecycle
