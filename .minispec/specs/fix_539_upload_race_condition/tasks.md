---
feature: fix_539_upload_race_condition
status: planned
created: 2026-11-20
chunk_size: adaptive
total_tasks: 10
estimated_lines: 570
---

# Prevent Edit/Save Races During File Upload: Tasks

## Overview

Implements `design.md`: read-only layer locking per file during upload (with a
layer tree indicator), GeoPackage checkpoint before upload, raster fingerprint
decision on completion, and a shared upload/download file lock keyed on
`(project_id, file_id)`. Tests are bundled with each task (unit tests only; no
E2E tests are proposed). Run unit tests and pre-commit before each commit.

## Task List

### Foundation

#### Task 1: Stable shared `sync_key(project_id, file_id)`
- **Estimate:** ~50 lines (incl. tests)
- **Files:** `rana_qgis_plugin/layer_management/sync_lock.py`, `rana_qgis_plugin/loader.py` (`:1792-1798`, `:1867-1875`, `:1912-1918`, `layers_for_keys` `:2030-2042`), `rana_qgis_plugin/workers/styling.py` (style items carry `file_id`), `tests/layer_management/`
- **Description:** Add `sync_key(project_id, file_id)` and use it everywhere a sync key is built or matched: data upload verify and acquire, style upload acquire and target lookup, `layers_for_keys`. Drops `descriptor_id` from the key, because the server assigns a new one on every upload. Style upload items get the ref's `file_id` if they do not have it yet.
- **Depends on:** None
- **Acceptance:** Data and style uploads of the same file still block each other; `layers_for_keys` finds the same layers as before for linked layers.
- **Evidence:** unit test that a layer ref and a folder-listing item for the same file give the same key, also with different or missing `descriptor_id`; existing loader/style tests pass.

#### Task 2: `layers_for_file` and `FileLock` / `lock_jobs`
- **Estimate:** ~130 lines (incl. tests)
- **Files:** new `rana_qgis_plugin/layer_management/upload_lock.py`, new `tests/layer_management/test_upload_lock.py`
- **Description:** `layers_for_file(path)` finds all project layers whose source resolves to the file (via `QgsProviderRegistry.decodeUri`, resolved paths; all tables of a GeoPackage). `FileLock` holds the sync key and the locked layer IDs; locking stores the previous read-only state in custom property `rana/upload_lock` and sets `setReadOnly(True)`. `release()` restores from the property and removes it, skipping removed layers, then releases the key; a `released` flag makes later calls do nothing, so a late call cannot free a key or layers taken by a newer lock on the same file. `lock_jobs(jobs, registry)` takes key + locks layers per job, drops jobs that cannot be locked (key held, layer editable), releases what it took if it fails part way, and returns `({sync_key: FileLock}, warnings)`. `restore_stale_upload_locks(project)` restores and clears any leftover `rana/upload_lock` (project saved mid-upload).
- **Depends on:** Task 1
- **Acceptance:** Matching works for `file.gpkg|layername=x`, shapefiles and non-matching files; refusal when a layer is editable; previous read-only state restored; second `release()` does nothing, also when a newer lock holds the same key; stale property cleaned up.
- **Evidence:** new unit tests pass.

#### Task 3: Per-file completion on the upload task
- **Estimate:** ~40 lines (incl. tests)
- **Files:** `rana_qgis_plugin/workers/upload.py`, `tests/workers/` (existing upload tests)
- **Description:** Add `sync_key` to `UploadJob` as `field(default=None, init=False, compare=False)` like `last_modified_key`; an init field with a default would break the required `source_path` of `ShapefileUploadJob`. Add a `file_completed(job)` signal to `FileUploadTask`, emitted after `finish_file_upload` and the `last_modified` write (`:251-261`).
- **Depends on:** None
- **Acceptance:** Signal is emitted once per successful file, not for failed or never-reached files.
- **Evidence:** unit test with a stubbed requests/`finish_file_upload` showing emissions; existing upload tests still pass.

### Core Implementation

#### Task 4: GeoPackage checkpoint before upload [P]
- **Estimate:** ~60 lines (incl. tests)
- **Files:** `rana_qgis_plugin/workers/upload.py` (preprocess for gpkg jobs), tests in `tests/workers/`
- **Description:** On the worker thread, open a separate `sqlite3` connection with a timeout and run `PRAGMA wal_checkpoint(TRUNCATE)`; retry a few times if the result is busy, then fail that file with a clear message. Skip for non-GeoPackage and shapefile jobs (converted first).
- **Depends on:** Task 3 (preprocess hook placement)
- **Acceptance:** Rows that exist only in `-wal` are in the main file afterwards; busy result leads to a failed file with message.
- **Evidence:** unit test using a temp GeoPackage in WAL mode with `wal_autocheckpoint=0`.

#### Task 5: Raster completion decision [P]
- **Estimate:** ~50 lines (incl. tests)
- **Files:** `rana_qgis_plugin/layer_management/raster_dirty_evaluator.py`, `rana_qgis_plugin/workers/upload.py`, `tests/layer_management/`
- **Description:** Small function taking the start fingerprint and the layer: equal -> `capture_raster_baseline`; different -> set dirty explicitly. Job stores the start fingerprint when prepared (extra `init=False` field on `UploadJob`).
- **Depends on:** Task 3 (job fields)
- **Acceptance:** Unchanged file ends clean with baseline; modified file ends dirty.
- **Evidence:** unit tests for both outcomes.

#### Task 6: Upload lock indicator [P]
- **Estimate:** ~60 lines (incl. tests)
- **Files:** `rana_qgis_plugin/layer_management/indicator_manager.py`, `tests/layer_management/`
- **Description:** Track `rana/upload_lock` in `_TRACKED_PROPERTY_KEYS`; show a lock indicator with tooltip "Uploading to Rana — read-only until the upload finishes" on layer nodes carrying it. Key managed indicators by node and kind so the dirty and upload indicators can coexist. Pick the icon from the QGIS theme (e.g. `/locked.svg`; verify it exists in QGIS 4).
- **Depends on:** Task 2 (property name)
- **Acceptance:** Indicator appears when the property is set and disappears when it is removed; dirty indicator unaffected.
- **Evidence:** unit tests on `IndicatorManager` with a real layer tree view.

#### Task 7a: Wire locking into `upload_existing_files` (core)
- **Estimate:** ~120 lines (incl. tests)
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/workers/upload.py` (`file_failed` emits the job), `tests/loader/`
- **Description:** Set `sync_key` on each prepared job. Call `lock_jobs` after all early returns (items empty, conflict abort/skip, no jobs, no task manager), only for files that have a job (fixes keys for skipped files). One try/except from lock to `addTask` releases all locks. Only `FileLock.release()` releases a data upload's keys: drop `task.rana_sync_keys` for data uploads and the key releases in `handle_sync_completed`/`taskTerminated` for them. `file_completed` handler (vector -> clean, raster -> Task 5, update `descriptor_id` from `task.updated_descriptors`, then release) and `file_failed` handler (log, release), each in try/finally, looking up `locks[job.sync_key]`. `taskCompleted`/`taskTerminated` call `release()` on all locks. Remove the data-sync state updates and `update_descriptor_ids` at task end for data uploads.
- **Depends on:** Tasks 2, 3, 5
- **Acceptance:** Per-file unlock as each file finishes; skipped/errored files never locked; failures, cancel and setup exceptions leave nothing locked or read-only; a task ending after its file was re-locked by a new upload leaves the new lock intact.
- **Evidence:** loader unit tests: lock released on completed, failed, terminated, and on exception during task setup; skipped job never locked; raster changed during upload is still dirty after `taskCompleted` (real `FileUploadTask`, network stubbed); re-locked file survives the old task's end. Manual test paths in Notes.

#### Task 7b: Pre-check and stale locks on project read
- **Estimate:** ~50 lines (incl. tests)
- **Files:** `rana_qgis_plugin/loader.py` (`upload_existing_files` start, `:1750`), `rana_qgis_plugin/rana_qgis_plugin.py`, `tests/loader/`
- **Description:** Pre-check for editable layers before `prepare_existing_file_upload` ("Save or discard your edits first."), so a refused file does not open an upload session. Call `restore_stale_upload_locks` on project read (`QgsProject.readProject`, connected in `initGui`, disconnected in `unload`). Drive-by: new-file upload shows "Downloading {name}" (`:1750`); change to "Uploading {name}".
- **Depends on:** Task 7a
- **Acceptance:** A file with a layer in edit mode is refused before preparing; a project saved mid-upload and reopened has nothing read-only.
- **Evidence:** loader unit test for the refusal (no `prepare_existing_file_upload` call). Manual: edit-mode refusal, save project during upload and reopen.

#### Task 8: Download takes the same file lock
- **Estimate:** ~70 lines (incl. tests)
- **Files:** `rana_qgis_plugin/loader.py` (`download_and_open` `:2245-2285`, folder dispatch `:2181-2191`), `tests/loader/`
- **Description:** After the `resolve_url` and `task_manager` early returns, take a `FileLock` with no layers for `sync_key(project["id"], file_item["id"])`; if the key is held by an upload show "`<file>` is being uploaded. Open it again when the upload has finished." and do not download. `download_and_open` runs one file per `DownloadTask`, so release in its `taskCompleted`/`taskTerminated`, with guarded setup. In folder opens, skip such files and report how many were skipped. An upload of a file being downloaded is refused by the existing message.
- **Depends on:** Task 1 (shared key), Tasks 2 and 7a (`FileLock`)
- **Acceptance:** No download starts while the file's upload key is held; key released after download success, failure and cancel.
- **Evidence:** unit tests for refusal, release paths, and folder skip count.

### Integration & Polish

#### Task 9: Manual verification and PR notes
- **Estimate:** ~0 lines (checklist)
- **Files:** none (PR description)
- **Description:** Run the manual QGIS checks from `design.md` and record results: multi-table GeoPackage locked/unlocked per file with lock indicator; batch unlock one by one; edit mode refusal; cancel and forced failure; skipped file never locked; close project / remove layer during upload; save project during upload and reopen; raster overwritten during upload stays dirty; commit, upload, download shows edits; reopen a file during its upload refused and folder skips it; style upload during data upload of the same file refused. Also check bytes 18-19 of a `.gpkg` after closing QGIS (WAL question in the design).
- **Depends on:** Tasks 1-8
- **Acceptance:** All checks pass or are filed as follow-ups.
- **Evidence:** checklist in the PR description. E2E tests are not added; propose them only with explicit permission.

## Notes

- Parallel: Tasks 1 and 3 are independent; Tasks 4 and 5 can run together after Task 3; Task 6 can run after Task 2.
- Task 7 is split into 7a (core wiring) and 7b (pre-check, stale locks, wording). Order of work: 2, 7a, 7b, 6, 8, with a review stop after each.
- Complexity check: one new module (`upload_lock.py`) plus its test file; everything else modifies existing files. The shared `sync_key` function has 4 call sites (data upload, style upload, `layers_for_keys`, download); extraction accepted by the engineer.
- Out of scope / deferred: locking layers for new-file uploads (unlikely; fix when it turns up), downloading over un-uploaded local edits, remote conflict detection (`If-Match`), unused server upload sessions after conflict skip/abort, edits by external programs.
- Style read-only locking is deferred: QGIS has no style equivalent of the vector provider read-only flag. Style uploads keep their file lock, but style changes remain possible and are outside the upload snapshot.
- Windows-only rare read failure on rollback-mode GeoPackages over 1 GB: a failed upload can be retried; no task.

## Progress
- [x] Task 1: Stable shared `sync_key(project_id, file_id)`
- [x] Task 2: `layers_for_file` and `FileLock` / `lock_jobs`
- [x] Task 3: Per-file completion on the upload task
- [x] Task 4: GeoPackage checkpoint before upload
- [x] Task 5: Raster completion decision
- [x] Task 6: Upload lock indicator
- [x] Task 7a: Wire locking into `upload_existing_files` (core)
- [x] Task 7b: Pre-check and stale locks on project read
- [x] Task 8: Download takes the same file lock
- [ ] Task 9: Manual verification and PR notes
