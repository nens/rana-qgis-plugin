---
feature: feat_454_open_generic_files
status: complete
created: 2026-08-18
decisions:
  - 20260818-1041-rana-layer-reference-storage.md
  - 20260818-1041-group-structure-reuse.md
  - 20260818-1041-save-data-file-level-only.md
  - 20260818-1041-download-task-symmetry.md
  - 20260818-1041-sync-in-progress-lock.md
  - 20260818-1041-dirty-tracking-vector-only.md
  - 20260818-1041-rename-delete-linking-local-session.md
  - 20260818-1041-close-project-sync-prompt.md
  - 20260818-1041-remote-change-lazy-guard.md
---

# Open Rana Files/Layers in QGIS & Sync Back Design

## Overview

Enable opening Rana files and layers (vector, raster) into the QGIS layer
panel — invoked via double-click or context menu on Browser items — with the
layer panel mirroring the Rana data-source tree structure
(`project/files/foo/bar.gpkg/layer_name`). Layer-panel items that originate
from Rana carry reference metadata (project id, file path, descriptor id,
layer id) enabling later "save style to Rana" / "save data to Rana" actions
from the layer panel's own context menu, with concurrency guards (QgsTask +
disabled menu while syncing), out-of-sync visibility, and safe behavior when
the underlying Rana file/folder is renamed or deleted — whether via this same
QGIS session or remotely by another user/session.

This is one design delivered in three independently shippable phases:

- **Phase 1** — Open files/layers into the layer panel (foundation)
- **Phase 2** — Save style/data back to Rana (sync task, dirty tracking, locking)
- **Phase 3** — Keep layer-panel references correct as Rana state changes
  (local-session linking + remote-change guard)

### Phase contract

| Phase | FRs delivered | SCs delivered | Not yet covered |
|-------|---------------|---------------|------------------|
| 1 | FR-001, FR-002, FR-003 | SC-001, SC-002 | Sync (FR-004..FR-007), reference integrity (FR-009..FR-011) and close-project sync (FR-008) not yet available — layers opened in Phase 1 have no rename/delete protection until Phase 3 ships |
| 2 | FR-004, FR-005, FR-006, FR-007 | SC-003, SC-004 | Reference integrity (FR-009..FR-011, SC-005) still absent; close-project guarantee (FR-008 / SC-006) deferred to Phase 3 |
| 3 | FR-008, FR-009, FR-010, FR-011 | SC-005, SC-006 | — |

## User Stories

- As a user, I want to double-click a Rana file/layer in the Browser panel
  so that it opens directly into my QGIS project, grouped the same way it
  appears in the Rana tree.
- As a user, I want to right-click a Rana file/folder (including multi-select)
  and choose "Open in QGIS" so I don't have to open items one at a time.
- As a user, I want to right-click a layer or file group in the layer panel
  that came from Rana and save my style/data edits back to Rana.
- As a user, I want to see when a layer's style or data has changed locally
  and hasn't been synced to Rana yet.
- As a user, when I close my project, I want to be warned if I have unsynced
  changes and be offered a chance to sync them all before closing.
- As a user, if a file I have open was renamed or moved within this same
  session, I want my layer to keep working without QGIS renaming my layer or
  losing my styling.
- As a user, if a file I have open was deleted or renamed by someone else
  (or in another session) and Rana no longer recognizes it, I want to be
  warned and have sync actions disabled rather than have my layer silently
  fail or disappear.

### Edge Cases

 - Opening a folder with many files or nested subfolders — see Phase 1 folder-open threshold (recursive traversal semantics described in Phase 1).
 - Opening the same file twice — reuses existing matching groups (matched by Rana reference metadata: project_id + full path segments), doesn't duplicate the group tree.
- Right-clicking "save data" on a single layer inside a multi-layer vector file — disabled; only available at file/group level (see Phase 2).
- Style change events firing very frequently (e.g., render tweaks) — dirty flag is idempotent, no debouncing needed.
- Raster files have no in-QGIS edit signal — "save data" for rasters has no dirty tracking, always enabled.
- File renamed/deleted through this same QGIS session — handled via existing Loader signals (Phase 3a).
- File renamed/deleted remotely (another session/user, or via Rana web UI) — cannot be observed proactively; handled via a lazy pre-save existence check (Phase 3b).
- Ancestor folder renamed/deleted (locally or remotely) — locally handled by the same Loader signal (prefix-remap contract); remotely, caught incidentally by the same lazy per-save existence check as a stale-path failure (no separate ancestor-detection logic needed).
- Closing the project while unsynced changes exist — prompt to sync all; note the underlying Qt/QGIS signal used is not cancelable, so "Cancel" can only mean "skip syncing now," not "abort closing."

## Phase 1 — Opening Files/Layers

### Invocation

- `QgsDataItem.handleDoubleClick()` implemented on `RanaFileDataItem` and
  `RanaLayerDataItem` — this is the native QGIS Browser mechanism, no manual
  tree-view signal wiring required.
- The existing (currently unwired) `FileAction.OPEN_IN_QGIS` context-menu
  `QAction` in `file_item.py` / `layer_item.py` is connected to the same open
  code path.
- Existing `FileAction` gating is reused unchanged: `OPEN_IN_QGIS` already
  only appears for `data_type in {vector, raster, threedi_schematisation}` —
  no new type/size guard needed.
 - Folder-level / multi-select open: the selection is traversed recursively — all files under the selected folder(s) and their subfolders at any depth are counted. If the resolved recursive file count is ≤10 and no nested folders are present, open all directly; if nested folders are present at any depth or the file count is larger, show a confirmation dialog with the resolved full recursive file count before proceeding.

### Download

Legacy already had a clean three-part structure for downloads
(`legacy/workers/download.py`), split by responsibility:

- **Downloader** (`BaseDownloader` / `RanaDownloader` / `RanaFileDownloader`)
  — knows the specifics of *what* to download and how to post-process it
  (e.g. `RanaFileDownloader` fetches the file via the tenant file URL and
  extracts/matches QML style files for vector/raster types).
- **Download context** (`AbstractDownloadContext` / `FileDownloadContext` /
  `TempDownloadContext`) — knows the specifics of *where* to download to
  (`local_dir`, `local_file_path`) and how to fetch the style zip for that
  context.
- **Download worker** — the actual execution unit that drives one or more
  downloaders. Legacy used `QThread` (`SingleFileDownloadWorker` /
  `BatchFileDownloadWorker`); this design ports that role to a new
  `DownloadTask(QgsTask)`, consistent with the existing `UploadTask` pattern
  and the "background transfer must not block the UI thread" rationale
  already established for uploads.

Concretely, for this feature:

- Reuse the existing `BaseDownloader`/`RanaDownloader`/`RanaFileDownloader`
  classes as-is (or a light adaptation) for the downloader role — no need to
  reinvent style-zip extraction or raster QML rescaling logic that's already
  proven there.
 - Security note / action item: legacy `workers/download.py`'s style-zip
   extraction logic will be adapted for the new open-cache layout. As part
   of task breakdown, the team MUST perform an extraction audit to ensure
   path-traversal safety (zip-slip checks) when extracting archives into the
   open cache directory.
- New `OpenFileDownloadContext(AbstractDownloadContext)` resolves
  `local_dir`/`local_file_path` under a new **open cache directory** (see
  below), analogous to legacy's `TempDownloadContext` but parameterized like
  `FileDownloadContext` (project, file id, descriptor id, data type) so the
  resulting path can be sanitized/structured consistently.
- New `DownloadTask(QgsTask)` replaces the `QThread`-based workers: accepts
  one or more `(downloader, download_context)` pairs, runs them
  sequentially, checks `isCanceled()` between files (mirroring
  `UploadTask.run()`), and emits `file_started`/`file_failed`/progress
  signals for the calling code (Browser action / folder-open flow) to
  surface via the message bar.
  - While a file's own download is in flight, re-triggering "open" for the
   same file/layer is a no-op (or shows "already opening") — prevents
   duplicate downloads of the same target. (Legacy's
   `BatchFileDownloadWorker.handle_existing()` de-duplication logic for
   batch opens can be reused/adapted for the folder-open / multi-select
   case.)
  - Downloads MUST write to a sibling `.part` path and atomically rename it
    to the final local path only after the download and post-processing
    succeed. Partial files MUST never be treated as completed downloads;
    checksum validation is intentionally out of scope for now.

#### Migration notes: modules moved out of legacy

As preparatory groundwork for this feature, three modules were moved out of
`legacy/` verbatim via `git mv` (preserving history/blame), ahead of being
adapted for the new architecture:

- `legacy/workers/download.py` → `workers/download.py`
- `legacy/workers/styling.py` → `workers/styling.py`
- `legacy/layer_manager.py` → `layer_manager.py`

(A fourth, `legacy/widgets/utils_icons.py`, turned out to already have an
identical non-legacy duplicate at `widgets/utils_icons.py` — the legacy copy
was deleted and the two remaining stray imports repointed, rather than
moved.)

**mypy consequence**: `mypy.ini` previously exempted all of `legacy/.*` via
`ignore_errors = True`. Moving these three files out of that exclusion
surfaced ~50 pre-existing latent type errors (`QgsProject | None` unguarded
access, missing return statements, loosely-typed dict access, etc.) that
were never actually introduced by this feature — they were always there,
just unchecked. Rather than fix them as a side effect of a pure move, or
re-widen the exclude back over non-legacy code, `mypy.ini` now carries
**per-module** `ignore_errors = True` entries for exactly these three moved
files, with a comment marking them as temporary:

```ini
# Moved out of legacy/ verbatim (git mv, pending adaptation as part of
# feat_454_open_generic_files); carry the same exemption legacy.* had until
# these are actually rewritten. Remove these entries once each file is
# adapted for the new architecture.
[mypy-rana_qgis_plugin.workers.download]
ignore_errors = True

[mypy-rana_qgis_plugin.workers.styling]
ignore_errors = True

[mypy-rana_qgis_plugin.layer_manager]
ignore_errors = True
```

**Action item for task breakdown**: each phase that adapts one of these
files (Phase 1 for `workers/download.py` and `layer_manager.py`, Phase 2 for
`workers/styling.py`) MUST remove its corresponding `mypy.ini` exemption as
part of that phase's definition of done — the exemption is a temporary
bridge, not a permanent carve-out, and should not survive past the file
actually being rewritten to the new `QgsTask`-based structure discussed
above.

#### Download cache directory

Uploads and the existing Rana file cache use `rana_cache_dir()`
(`utils/settings.py`), defaulting to `~/Rana` — a persistent, user-visible
location intended for files the user has deliberately downloaded/cached.
Files opened via "Open in QGIS" are a different kind of artifact: a
working copy backing a layer-panel item, conceptually disposable, and not
something the user needs to browse to directly. These should not default
into the same user-facing folder.

New setting, mirroring `rana_cache_dir()`'s pattern but with a
temp-oriented default:

```python
def rana_open_cache_dir() -> str:
    default = str(Path(tempfile.gettempdir()) / "rana_downloads")
    return QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/open_cache_dir", default)

def set_rana_open_cache_dir(cache_dir: str) -> None:
    QgsSettings().setValue(f"{RANA_SETTINGS_ENTRY}/open_cache_dir", cache_dir)
```

- Defaults to the OS temp directory (`tempfile.gettempdir()` — resolves to
  `/tmp` on Linux, `%TEMP%` on Windows, equivalent on macOS), same base
  legacy's `TempDownloadContext` already used
- Still overridable via `QgsSettings`, consistent with how `rana_cache_dir`
  is user-configurable
- Kept separate from `rana_cache_dir` so cleanup/retention policy for
  "working copies backing open layers" can differ from "user's deliberately
  cached files" without cross-affecting either
 - No active cleanup policy: this design does not implement an active
   retention/eviction policy for `rana_open_cache_dir()`; it relies on the
   operating system's temporary-directory lifecycle (e.g., cleared on reboot
   per OS conventions). Future size-based eviction or explicit cleanup is
   potential follow-up work (out of scope for this design).

### Layer-panel structure

 - The datasource tree structure is the source of truth for the layer-panel
   group hierarchy. The caller (data item action handler) derives `parents`
   — a list of display-name path segments (`[project_name, "files",
   folder..., file_name]`) — from the data item's own attributes
   (`project["name"]`, `file_item["id"].split("/")`), and passes them
   together with a `RanaLayerRef` to a standalone group-builder function.
   No subclass polymorphism is needed to derive the hierarchy.
 - Group hierarchy is built by a find-or-create walk over `QgsLayerTreeGroup`
   per path segment, with group identity based on Rana reference metadata
   (custom property on group nodes: `rana/project_id` + `rana/path_segment`)
   rather than display name alone — avoiding collisions when files/folders
   share display names across different Rana projects or paths. Repeated
   opens reuse existing matching groups.
 - The legacy `LayerManager` class and its `FileLayerManager` /
   `PublicationLayerManager` subclasses remain in `layer_manager.py` as
   reference until all functionality they cover (WMS, scenario,
   schematisation, publications) is ported. New code does not extend or
   instantiate them.
 - Phase 1 scope: only raster files, vector files, and individual vector
   layers. WMS, scenario, and schematisation support will be implemented
   in future features.
- Vector files: one `QgsVectorLayer` per Rana layer, matching the
  `RanaLayerDataItem` children shown in the Browser (`ogr` provider,
  `path|layername=...` URI).
- Raster files: a single `QgsRasterLayer` per file (raster files have no
  sub-layers in the current Browser model — only `data_type == "vector"`
  files are `Fertile`/expandable).

### Reference data storage

- New helper module (e.g. `utils/rana_layer_refs.py`) wrapping
  `QgsMapLayer.setCustomProperty()` / `customProperty()`:
  - `set_rana_refs(layer, project_id, file_path, descriptor_id=None, layer_id=None)`
  - `get_rana_refs(layer) -> RanaLayerRef | None`
  - `is_rana_linked(layer) -> bool`
- Chosen over an external registry because `customProperty` values persist
  automatically with the `.qgz`/`.qgs` project file, and there's no
  secondary structure to keep in sync when the user manually removes/renames
  layers in the panel.
- Stored fields: `project_id`, `file_path` (this is what the codebase calls
  `file_item["id"]` — a path string, not a stable UUID), `descriptor_id`
  (stable UUID, used for vector-file layer/style lookups), and `layer_id`
  (for the specific vector layer, where applicable).

## Phase 2 — Save Style / Save Data Back to Rana

### Context menu

- New `QgsLayerTreeViewMenuProvider` (or a `contextMenuAboutToShow` hook on
  `iface.layerTreeView()`) adds "Save style to Rana" and "Save data to Rana"
  entries for layers/groups where `is_rana_linked()` is true.
- **Save style**: available per-layer (exports the layer's QML, uploads via
  `upload_file_styling(descriptor_id, [qml])`) and at file/group level
  (bundles all layers' QML files in one call). Feasible at both
  granularities because the styles endpoint accepts a named file per layer.
- **Save data**: **file-level only**. The upload API
  (`start_file_upload`/`finish_file_upload`) replaces the whole file; there
  is no partial per-layer update. The action is disabled/hidden on
  individual layer items inside a multi-layer vector file — only available
  on the file-level group/node — to avoid implying a partial save that
  isn't possible and to avoid silently re-uploading sibling layers'
  unrelated state.

### Sync execution & locking

 - Runs as a `SyncTask(QgsTask)`. Locking is implemented via a central
   registry keyed by the canonical Rana file reference (e.g. `(project_id,
   descriptor_id)` or equivalent). Concurrent save attempts that target the
   same underlying Rana file (even if different layer/group items in the
   layer tree reference it) are blocked by this central lock. The menu
   provider consults the central registry (a small manager class or module
   level dict) to decide whether rana-related actions should be disabled for
   a given layer/group. A per-layer `rana/sync_in_progress` customProperty
   may still be maintained as a derived/display flag, but it is not the
   source-of-truth for locking.

### Dirty-state tracking

 - Vector layers: `afterCommitChanges` sets a `rana/data_dirty` flag;
   `styleChanged` sets a `rana/style_dirty` flag (any layer type). Note:
   `editingStopped` is intentionally not used because it can fire on
   rollback/cancel without an actual commit, producing false-positive dirty
   flags. Flags are idempotent (already-dirty stays dirty) and cleared only
   on successful sync of that aspect.
- Raster layers: no `data_dirty` tracking — QGIS has no raster edit-tracking
  signal and no cheap way to detect external on-disk changes, so "save data"
  for rasters stays always-enabled rather than gated on a flag that can't be
  reliably computed.
- Dirty state is surfaced visually in the layer tree (exact treatment — icon
  decoration vs. name badge vs. tooltip — left to implementation).

## Phase 3 — Keeping Layer-Panel References In Sync With Rana

Two independent mechanisms are needed, because Rana state can change through
this session (observable) or through another session/user (not observable).

### 3a. Local-session linking

- A lightweight listener subscribes to the existing `Loader.item_renamed(old_path, new_path, is_folder)` and `Loader.item_deleted(path, is_folder)` signals (already documented contract: prefix-based path remapping, `.minispec/knowledge/decisions/20260814-1002-prefix-based-path-remapping-contract.md`). These fire only for renames/deletes performed through this same browser/session's Loader.
- On rename: iterate `QgsProject.instance().mapLayers()` for rana-linked
  layers whose stored `file_path` starts with `old_path`; remap the prefix
  to `new_path`. **Layer display name and group names in the panel are never
  changed** — only the stored reference is updated.
- On delete: clear rana refs on affected layers (any layer whose stored
  `file_path` starts with the deleted path) — this disables rana context
  menu actions for those layers. **The layer itself is never removed** from
  the panel.

### 3b. Remote-change guard (lazy, check-on-save only)

Research finding (`@rana-api`): the Rana backend offers **no push/webhook/
websocket/SSE/polling-friendly change feed**. Renames/deletes performed by
another user or session are fundamentally unobservable except by directly
asking about the specific file. Also clarified: `descriptor_id` is a stable
UUID unaffected by rename/move (descriptor lookup is ID-based, no path
involved); `file_path` (`file_item["id"]`) is a path string that does go
stale on rename/move (rename/move endpoints are path-based).

Given no proactive detection is possible, the guard is deliberately lazy and
runs **only immediately before executing a save**, not on context-menu open
(rejected — an extra GET per menu-open was judged too chatty for a
seldom-triggered failure mode) and not via background polling:

 - **Save-style click** → first call `GET /tenants/{tenant}/file-descriptors/{descriptor_id}` (stable-ID check).
 - **Save-data click** → first call `GET /tenants/{tenant}/projects/{project_id}/files/stat?path=<stored file_path>` (path-based check, matching the path-based upload endpoint).
 - Failure taxonomy and handling:
    - Not-found errors (authoritative): errors that unambiguously indicate the file/descriptor does not exist (e.g. documented HTTP 404/410 or any Rana API response explicitly documented as "does not exist"). Treat these as authoritative: clear the layer's rana refs, disable its rana context-menu actions going forward, show a warning ("This file no longer exists in Rana — syncing has been disabled for this layer/group."), and abort the requested save without queuing a `StyleUploadTask` or `FileUploadTask`. This is terminal for the stored reference; it is not retryable.
    - Generic / transient errors: network failures, timeouts, 5xx responses, authentication errors, or any non-authoritative failure. Preserve the layer's rana refs and do NOT disable sync actions long-term. Warn the user that the existence check failed (e.g. "Could not verify file exists in Rana — try again"), and abort the save for this attempt only. The user may retry the save later, which re-runs the guard.
 - These checks cover remote delete, remote rename (stale stored `file_path`), and remote ancestor-folder rename/delete: an authoritative not-found result is sufficient to treat the layer as stale and disable syncing; transient failures are retryable and leave refs intact.
 - Implementation risk / validation note: if the Rana API's real-world error responses do not cleanly distinguish authoritative not-found results (404/410) from transient failures, this ambiguity MUST be resolved during task breakdown — flag this as an implementation risk.
  - Close-time syncing is intentionally deferred; future automatic sync-on-edit work is expected to reduce the need for a close warning.

### Quit warning for unsynced Rana files

- The first implementation only handles the main-window application close
  event, not `QgsProject.instance().aboutToBeCleared`. New Project, Open
  Project, and project-close behavior remain under QGIS's native flow and are
  intentionally unchanged.
- Before quitting, scan Rana-linked layers for `rana/data_dirty` or
  `rana/style_dirty`. If any exist, show a simple warning listing the affected
  filenames and offer `Cancel` or `Quit anyway`.
- `Cancel` calls `QCloseEvent.ignore()` and prevents QGIS from quitting.
  `Quit anyway` leaves all state unchanged and allows normal shutdown.
- This task does not save the QGIS project, upload files or styles, or change
  local edit handling. Future automatic sync-on-edit work is expected to
  reduce or remove the need for this warning.
- The close warning is deferred in favor of the future automatic sync-on-edit
  feature. Dirty-state tracking remains available for sync-action gating and
  successful-sync cleanup, but no quit-time warning is implemented here.

## Key Entities

- **RanaLayerRef**: `{project_id, file_path, descriptor_id?, layer_id?}` — stored as `QgsMapLayer` custom properties (`rana/project_id`, `rana/file_path`, `rana/descriptor_id`, `rana/layer_id`), persisted with the `.qgz` project.
- **Sync flags**: `rana/sync_in_progress`, `rana/data_dirty`, `rana/style_dirty` — additional custom properties driving menu-enablement and dirty-state display.
 - **Sync flags / locking**: locking is driven by a central registry keyed by the canonical Rana file reference (e.g. `(project_id, descriptor_id)`) which is the source-of-truth for whether a given underlying file is locked for sync. A per-layer `rana/sync_in_progress` customProperty may still be written as a derived/display flag, alongside `rana/data_dirty` and `rana/style_dirty`, but the menu provider and sync coordination logic MUST consult the central lock registry rather than per-layer properties when deciding to disable actions or queue syncs.
- **DownloadTask / FileUploadTask / StyleUploadTask**: `QgsTask` subclasses for background download and background style/data upload.

## Requirements

### Functional Requirements

- **FR-001**: Users MUST be able to open a Rana vector or raster file, or an individual layer within a multi-layer vector file, into the QGIS layer panel via double-click or context menu ("Open in QGIS").
- **FR-002**: Opened layers MUST appear in the layer panel grouped to mirror the Rana tree path (`project/files/.../file/layer`), reusing existing matching groups rather than duplicating them on repeat opens.
- **FR-003**: System MUST attach retrievable Rana reference data (project id, file path, descriptor id, layer id where applicable) to each opened layer, persisted with the QGIS project.
- **FR-004**: Users MUST be able to save a rana-linked layer's or file's style back to Rana, at both per-layer and per-file granularity.
- **FR-005**: Users MUST be able to save a rana-linked file's data back to Rana at file level only; this action MUST NOT be offered for an individual layer inside a multi-layer vector file.
- **FR-006**: Save operations MUST run as background `QgsTask`s and MUST prevent a second save from being started for the same layer/file while one is in progress (context-menu actions disabled during sync).
- **FR-007**: System MUST visually indicate when a rana-linked layer has local style or data changes not yet synced to Rana (vector layers only for data; all layer types for style).
- **FR-008**: On project close, System MUST warn about unsynced changes and offer an option to sync all before proceeding, with the caveat that closing itself cannot be blocked/canceled.
- **FR-009**: When a file/folder is renamed within the same QGIS session (via this plugin's own Loader), rana-linked layers under that path MUST have their stored reference path updated automatically; the layer's display name and panel group names MUST NOT change.
- **FR-010**: When a file/folder is deleted within the same QGIS session, rana-linked layers under that path MUST have their rana reference cleared (disabling sync actions); the layer itself MUST NOT be removed from the panel.
- **FR-011**: Immediately before executing a save action, System MUST verify the underlying Rana file/descriptor still exists (lazy check). If the check returns an authoritative "not found" result, System MUST clear the layer's rana reference, disable its sync actions, and warn the user. If the check fails due to a transient or non-authoritative error, System MUST preserve the layer's rana refs, warn the user that verification failed and abort the save for this attempt only (the user may retry the save which re-runs the guard). This covers remote renames/deletes and remote ancestor-folder renames/deletes for authoritative not-found results without needing separate detection logic for each case; transient failures are treated as retryable.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can open a Rana vector or raster file into QGIS via double-click or context menu in under the time it takes to download the file, with no manual group/layer setup required.
- **SC-002**: Repeated opens of files under the same Rana folder do not create duplicate layer-tree groups.
- **SC-003**: A user can save style and/or data changes back to Rana from the layer panel context menu without needing to use the Browser panel.
- **SC-004**: Attempting a second save on a layer/file already syncing is blocked at the UI level (menu item disabled), not merely rejected after submission.
- **SC-005**: If a save attempt determines (authoritatively) that the underlying Rana file has been deleted or renamed remotely, the layer's sync actions are disabled and the user is warned — without the layer disappearing or the save silently failing. If the pre-save check fails due to a transient/non-authoritative error, the layer's refs are preserved, the user is warned that verification failed, and the save is aborted for that attempt only (user may retry).
- **SC-006**: Closing a project with unsynced rana-linked changes always surfaces a warning/sync-all prompt before the project state is lost.

## Out of Scope

- Visual treatment of the dirty-state indicator (implementation detail).
- Conflict resolution when the Rana-side file has changed since it was opened locally (not addressed — potential future design).
- Proactive/background detection of remote changes (rejected in favor of lazy per-save check; see Phase 3b).
