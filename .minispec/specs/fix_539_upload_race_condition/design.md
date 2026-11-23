---
feature: fix_539_upload_race_condition
status: planned
created: 2026-11-20
decisions:
  - 20261120-1000-lock-layers-during-upload
  - 20261120-1001-uploads-and-downloads-share-file-lock
  - 20261120-1002-raster-dirty-after-upload-by-fingerprint
---

# Prevent Edit/Save Races During File Upload

## Overview

`FileUploadTask.run` streams the live local file to Rana
(`workers/upload.py:244-250`) with no snapshot, lock or post-check. A save during
the upload can send a mixed file, and completion then marks the layer clean
(`loader.py:2048-2055`) even though newer edits were never sent. Opening the
same file from Rana during an upload downloads over the file in place
(`workers/download.py:240`).

Fix: make vector layers of a file read-only for the duration of its data upload,
make downloads and uploads of the same file mutually exclusive, and decide
raster clean/dirty state by comparing fingerprints. No file copies are made (files can be hundreds of MB).

Style uploads currently keep their existing batch file lock, but do not make
layers read-only. QGIS has no equivalent style-read-only flag: the vector
layer read-only setting hides data editing controls but does not disable the
layer-properties style editors. A future style lock would need either UI
interception or a style snapshot-and-restore guard. For now, style changes
during a style upload are allowed and are not part of that upload's snapshot.

## User Stories

- As a user, I want my layers to be locked clearly while they upload so I cannot
  save edits that end up half-uploaded or silently lost.
- As a user uploading many files, I want each file's layers to unlock as soon as
  that file is done, not when the whole batch finishes.
- As a user, I want recent GeoPackage edits to be included in the upload.
- As a user, I want a raster changed during upload to stay marked dirty.

## Components

### Per-file completion in `FileUploadTask` (`workers/upload.py`)

One task handles a batch of jobs sequentially (`:238`); completion is only
reported per task. Add a `file_completed(job)` signal, emitted after
`finish_file_upload` and the `last_modified` write (`:251-261`). Existing
`file_failed` is already per file (`loader.py:1882`).

### Per-file sync keys (`loader.py`, `layer_management/sync_lock.py`)

Replace the inline key construction with one shared function
`sync_key(project_id, file_id)` in `sync_lock.py`, used by data uploads
(`loader.py:1792-1798`, `:1867-1875`), `layers_for_keys` (`:2030-2042`), style
uploads (`:1912-1918`) and downloads. Today the key is
`(project_id, descriptor_id or file_id)`, but the server assigns a new
`descriptor_id` on every upload (`update_descriptor_ids`, `:2061`), so the
layer's stored ref and a folder listing can hold different values for the same
file and the lock would silently not apply. `file_id` (the path within the
project) is stable for the duration of an upload. Style upload items need the
ref's `file_id` for this (add the field if missing). For data uploads and
downloads, keys are acquired and released per file through a `FileLock` (see
Lock Lifecycle); style uploads keep their per-batch keys. Fix the leak between
`acquire_sync_keys` (`:1876`) and `addTask` (`:1901`): wrap in try/except,
release locks on error.

### `layers_for_file(path)` (new, `layer_management/`)

Returns every project layer whose source resolves to the file, using
`QgsProviderRegistry.decodeUri` and resolved path comparison. This covers all
tables of a GeoPackage. Do not reuse the substring match in
`utils/generic.py:229-257` (`get_editable_layers_for_file`).

### Layer locking (new, `layer_management/`)

Main thread, before the task starts:
- If any layer from `layers_for_file` is editable, refuse the upload:
  "Save or discard your edits first."
- Otherwise store each layer's previous read-only state in the custom property
  `rana/upload_lock` and call `setReadOnly(True)`.

Unlock by layer ID (skip removed layers): restore the read-only state from the
property and remove it, on `file_completed`, `file_failed`, task termination,
and the setup-error path. Applies to uploads of existing (Rana-linked) files
only; see Out of Scope.

Custom properties (and possibly the read-only flag) are saved with the project.
If the project is saved during an upload, the lock would be persisted, so on
project read any layer still carrying `rana/upload_lock` is restored and the
property removed.

### Upload lock indicator (`layer_management/indicator_manager.py`)

Constitution I requires telling the user why a layer is locked. The existing
`IndicatorManager` already reacts to custom property changes; add
`rana/upload_lock` to the tracked keys and show a second indicator (lock icon,
tooltip "Uploading to Rana — read-only until the upload finishes") on layers
that carry it. The managed-indicator bookkeeping becomes keyed by node and
indicator kind, so the dirty and upload indicators can coexist. Layer nodes
only, no group indicator.

### Raster dirty state (`loader.py:2044-2059`, `raster_dirty_evaluator.py`)

Store `fingerprint_file(path)` on the job when it is prepared (main thread). On
`file_completed`, a small testable function compares it with the current
fingerprint: equal -> `capture_raster_baseline`; different -> set raster dirty
explicitly (the file watcher's debounced check may not have run yet). Vector
layers are set clean in the same per-file handler; the `loader.py:2877`
baseline call (open file) is unchanged.

Data sync state is set **only** in the per-file handler. `handle_sync_completed`
(`loader.py:2044-2059`) must stop calling `capture_raster_baseline` /
`set_data_sync_state` for data uploads; otherwise it runs after the per-file
handler at task end and turns a raster that changed during upload back to clean.
For data uploads it keeps only releasing leftover locks and showing the message.

### Download lock (`loader.py`, `download_and_open`)

Take the per-file key before starting a `DownloadTask`; if held by an upload,
show "`<file>` is being uploaded. Open it again when the upload has finished."
and do not download. Release on download success, failure and cancel. In folder
opens (`resolve`/dispatch, `loader.py:2181`), skip such files and report how
many were skipped.

## Data Model

No persisted data changes intended. Runtime only: per-job start fingerprint
(rasters) and sync key, and the `rana/upload_lock` layer custom property
(previous read-only state) for the duration of a file's upload. It is cleaned
up on project read if a project was saved mid-upload.

## Out of Scope

- Edits made outside QGIS, and external writes to a raster during upload.
- Warning about unsaved edits beyond refusing the upload.
- Remote conflict detection (`If-Match`/etag on the PUT).
- Downloading over local edits that have not been uploaded yet (separate issue).
- Layers added to the project during an upload other than via Rana "open"
  (the plugin does not support dragging Rana file items).
- Locking layers for new-file uploads (`upload_files`). A local file picked in
  the upload dialog that is also open as a layer is unlikely; fix it if it
  turns up.

## Testing

Unit:
- `layers_for_file`: GeoPackage with `|layername=`, shapefile, non-matching file.
- Lock/unlock: previous read-only state restored, removed layers skipped,
  upload refused when a layer is editable.
- Raster decision: matching vs changed fingerprint.
- Raster changed during upload is still dirty after `taskCompleted`
  (`handle_sync_completed` does not override the per-file decision).
- Download refused while the upload key is held; key released afterwards.
- `sync_key`: a layer ref and a folder-listing item for the same file produce
  the same key, also when their `descriptor_id`s differ or one is missing.
- Indicator: layer with `rana/upload_lock` shows the upload indicator, which is
  removed on release; a dirty layer can show both indicators.
- Project read with a stale `rana/upload_lock`: read-only state restored,
  property removed.
- `lock_jobs`: a job whose key is already held is dropped; a failure part way
  releases what was taken; `FileLock.release()` twice is harmless.
- Ownership: after file A's lock is released and a new lock on A is taken, a
  second `release()` of the old lock (task-end safety net) leaves the new key
  held and the layers read-only.

Manual (QGIS):
- Upload a multi-table GeoPackage: all its layers read-only, unlocked as soon as
  that file finishes.
- Upload a batch: layers unlock file by file, not at the end.
- Batch where one file is skipped (conflict "Skip") or errors during
  preparation: its layers are never locked.
- Close the project / remove a layer during an upload: no error, nothing left
  read-only afterwards.
- Start upload while a layer is in edit mode: refused with message.
- During upload, locked layers show the lock indicator with its tooltip.
- Save the project during an upload, reopen it: nothing read-only, no lock
  indicator.
- Cancel mid-batch and force a failure: everything unlocked.
- Overwrite a raster during upload: stays dirty afterwards.
- Commit edits, upload, download again: edits are present.
- Open a file from Rana during its upload: refused with message; opening a
  folder skips it and reports the count.

## Lock Lifecycle and Early-Return Paths

Two existing problems in `upload_existing_files` (`loader.py:1784-1901`) must be
fixed as part of this, because layer locking makes them visible to the user
(a layer stuck read-only):

1. Keys are acquired for all `verified_items` (`:1867-1876`), but `jobs` can be a
   subset (remote-newer file skipped, preparation error, conflict skipped).
   Skipped files stay locked until the task ends. Keys and layer locks must be
   per *job*, so each `UploadJob` gets a `sync_key` (`local_path` is used for
   `layers_for_file`).
2. Between `acquire_sync_keys` (`:1876`) and `addTask` (`:1901`) nothing
   releases keys if an exception is raised.

Rules:

- **Acquire as late as possible.** Locking (sync keys + read-only layers) happens
  in one place, after every early return and dialog: after `verified_items`
  is empty, conflict `ABORT`/`SKIP`, `not jobs`, and `task_manager is None`
  (`:1846-1848`, `:1860-1866`). Those paths therefore never hold a lock and need
  no cleanup. The same ordering applies to `download_and_open` (`resolve_url`
  failure `:2254-2262`,
  `task_manager is None` `:2264-2267`).
- **Single helper, all-or-nothing.** A function `lock_jobs(jobs)` takes the key
  and read-only-locks the layers of each job and returns a
  `{sync_key: FileLock}` dict with one entry per job it managed to lock. A job
  that cannot be locked (key already held, or a layer became editable since the
  pre-check) is dropped with a warning and not uploaded. If nothing remains,
  return without creating a task. If locking raises part way, it releases what
  it already took.
- **One owner per lock.** The registry does not know who holds a key, so a
  stray release can free a key (and restore layers) that a *later* upload of
  the same file has taken in the meantime. Therefore a file's key and layers
  are released **only** by its own `FileLock.release()`, and only once: the
  `FileLock` has a `released` flag and a second call does nothing. Data
  uploads do not use `task.rana_sync_keys`; neither `handle_sync_completed`
  nor `taskTerminated` releases keys for them directly.
- **Handlers find their lock by key.** `file_completed` and `file_failed` both
  emit the `UploadJob` (today `file_failed` emits a path string), and the
  handlers look up `locks[job.sync_key]`.
- **Per-file completion does all per-file work.** Set the sync state (vector
  clean, raster by fingerprint) and update the layer's `descriptor_id` from
  `task.updated_descriptors` before releasing. `update_descriptor_ids` no longer
  runs at task end for data uploads; otherwise a new upload of the same file
  could start in between with a stale `descriptor_id`.
- **Cheap pre-check before preparing.** Check "layer in edit mode" at the top of
  `upload_existing_files`, before `prepare_existing_file_upload`, so a refused
  file does not open an upload session on the server. The check is repeated
  inside `lock_jobs` because modal conflict dialogs run in between.
- **`FileLock.release()`** releases the key and restores read-only state by
  layer ID, skipping layers that no longer exist (removed layer, project
  closed). It does nothing when called again.
- **Task setup guarded.** Everything from the `lock_jobs` call to
  `task_manager.addTask` is in try/except; on any exception all `FileLock`s are
  released, an error is shown, and the exception is logged.
- **Release triggers per file:** `file_completed` and `file_failed`, each in
  try/finally so a failing handler cannot leave the lock behind.
- **Release triggers per task (safety net):** `taskCompleted` and
  `taskTerminated` call `release()` on every `FileLock` of the task; for files
  already finished this does nothing. This covers cancellation (including
  between files: `run()` returns on `isCanceled()`), an uncaught exception in
  `run()`, and files never reached because an earlier file failed.
- **Downloads** use the same `FileLock`, with no layers (it only holds the key).
  `download_and_open` runs one file per `DownloadTask`, so per file equals per
  task: take it after the early returns and release it in
  `taskCompleted`/`taskTerminated`.

Known leftover, not fixed here: `prepare_existing_file_upload` starts an upload
session on the server before the conflict dialog, so choosing skip or abort
leaves an unused session. This is existing behaviour and harmless to local
state.

## Open Questions

- Windows only: a plain read of a rollback-mode GeoPackage over 1 GB can fail
  transiently if a commit happens at that moment. Locked layers make this
  unlikely; a failed upload can simply be retried.
