---
feature: feat_470_file_sync
status: planned
created: 2026-10-14
decisions:
  - 20261014-close-sync-prompt-unified-hook
  - 20261014-dirty-state-layer-tree-indicator
  - 20261014-native-dirty-property-notification
---

# Unsynced Rana Changes Visibility

## Overview

Make locally-dirty (not-yet-synced-to-Rana) raster and vector layers visible
in the QGIS layer tree, and warn the user about unsynced changes whenever the
project is about to go away — switching projects or quitting QGIS. This picks
up two items explicitly deferred by `feat_454_open_generic_files`: the visual
treatment of the dirty-state indicator (listed there as out of scope), and the
close-time warning (deferred "in favor of the future automatic sync-on-edit
feature," never implemented).

Builds entirely on existing dirty-state tracking
(`layer_management/dirty_tracking.py`, `rana/data_dirty` / `rana/style_dirty`
custom properties, vector-only data tracking / all-types style tracking per
`20260818-1041-dirty-tracking-vector-only.md`) and the existing fire-and-forget
sync methods on `Loader` (`upload_existing_files`, `upload_styles`) and
`LayerTreeMenuProvider` (`save_style`, `save_data`). No new upload machinery is
introduced.

## User Stories

- As a user, I want to see at a glance which layers in my panel have local
  style or data changes not yet synced to Rana, including when their
  containing group is collapsed.
- As a user, when I close my current project or quit QGIS with unsynced
  changes, I want to be warned and given the option to sync everything before
  proceeding, understanding that the close/quit itself cannot be blocked.

### Edge Cases

- No dirty rana-linked layers exist at close time — no dialog shown.
- Raster "data dirty" has no reliable signal (per
  `20260818-1041-dirty-tracking-vector-only.md`) — rasters never show a data
  indicator and are never included in the close-prompt's data-sync set; only
  their style-dirty state is tracked.
- A layer or group is removed from the panel after an indicator was attached —
  the indicator must be explicitly removed (`QgsLayerTreeView.removeIndicator`
  does not auto-purge); this is bookkeeping only, not a user-facing warning.
- Quitting QGIS triggers `QgsProject.aboutToBeCleared` as part of its own
  shutdown sequence — handled naturally since quitting is a superset of
  closing the project; no separate quit-specific hook or dedup logic needed.
- "Sync now" at close time is fire-and-forget: if QGIS exits before a
  background upload task completes, the sync may be incomplete. Accepted
  tradeoff (see decision) rather than blocking the UI.

## Components

### `layer_management/indicator_manager.py` (new)

Manages `QgsLayerTreeViewIndicator` lifecycle for dirty state:

- Listens to the layer's native `customPropertyChanged(key)` signal, filtering
  for `rana/data_dirty` and `rana/style_dirty`. Existing dirty-tracking
  callbacks remain the only listeners to `afterCommitChanges` and
  `styleChanged`; the indicator manager reacts after those callbacks update
  the custom properties. Removing a dirty property after successful sync
  triggers the same notification path and clears the badge.
- Observes layers added to the project while the plugin is running and starts
  indicator tracking for them. Scanning layers that were already present at
  plugin startup is not required for this feature.
- Listens for layer/group removal to remove now-orphaned indicator objects
  (cleanup only — no warning dialog here, see Out of Scope).
- One generic icon/tooltip ("Has unsynced changes to Rana") regardless of
  whether it's style, data, or both — no distinction surfaced visually.
- Click behavior: tooltip only. Does not trigger a sync.
- Installed/torn down alongside the plugin's existing `initGui`/`unload`
  lifecycle in `rana_qgis_plugin.py`.

### `layer_management/close_sync_prompt.py` (new)

- Connects to `QgsProject.instance().aboutToBeCleared` (single hook, covers
  both quitting QGIS and switching/closing projects — quitting clears the
  project as part of its own shutdown, so no separate mechanism is needed).
- On fire: scans the layer tree's root group for rana-linked file groups with
  style-dirty or data-dirty content (reusing
  `LayerTreeMenuProvider.file_groups` / `collect_all_layers` and
  `is_style_dirty` / `is_data_dirty`), building two filtered group lists
  (style-dirty, data-dirty — same split `LayerTreeMenuProvider` already uses
  for its own menu actions).
- If both lists are empty, does nothing (no dialog).
- Otherwise shows a dialog listing affected file names with two actions:
  "Sync now" and "Continue without syncing." There is no "Cancel" — the
  underlying signal cannot abort the close, so a button implying it could
  would be misleading.
- "Sync now" calls the existing
  `LayerTreeMenuProvider.save_style(style_dirty_groups)` and
  `.save_data(data_dirty_groups)` as-is (same fire-and-forget calls the
  context menu already uses) — no blocking, no progress dialog, no new
  upload/task code.

### `LayerTreeMenuProvider` (`layer_tree_menu.py`)

- Rename `_collect_all_layers` → `collect_all_layers` (drop the leading
  underscore; per repo convention, visibility is expressed through
  documentation/imports, not name-mangling) so `close_sync_prompt.py` can call
  it directly alongside the already-public `file_groups`. No further
  extraction — both helpers stay on `LayerTreeMenuProvider` as staticmethods.

## Key Entities

- **Dirty flags** (existing, unchanged): `rana/data_dirty` (vector only),
  `rana/style_dirty` (all layer types) — `layer_management/dirty_tracking.py`.
- **Dirty-state notification** (native): `QgsMapLayer.customPropertyChanged`
  reports changes/removals to those flags; there is no duplicate dirty-state
  store or additional Loader signal.
- **Indicator**: `QgsLayerTreeViewIndicator` instance tracked per layer/group
  node by `IndicatorManager`, not persisted (created for layers added while
  the plugin is running as they become dirty).

## Requirements

### Functional Requirements

- **FR-001**: Users MUST see a visual badge on any layer-tree node (layer or
  ancestor group) backing a rana-linked layer with `rana/data_dirty` or
  `rana/style_dirty` set.
- **FR-002**: Badges MUST reflect current dirty state without stale data —
  appearing promptly when a tracked edit/style-change signal fires, and
  disappearing promptly after a successful sync of that layer.
- **FR-003**: On project close (including quitting QGIS), if any rana-linked
  layer has unsynced style or data changes, System MUST warn the user and
  offer to sync all dirty items before the close proceeds.
- **FR-004**: The close warning MUST NOT claim to be able to cancel the
  close/quit — only "sync now" vs. "continue without syncing" are offered.
- **FR-005**: "Sync now" MUST reuse existing per-file style/data upload
  entry points unchanged; this feature MUST NOT introduce new upload,
  locking, or remote-change-guard logic.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can tell, without expanding every group, that a
  collapsed folder/file group contains at least one unsynced layer.
- **SC-002**: Closing a project or quitting QGIS with unsynced rana-linked
  changes always surfaces exactly one warning (never zero when dirty state
  exists, never two for the same close/quit action).
- **SC-003**: Choosing "Sync now" from the warning results in the same
  upload behavior (conflict handling, locking, remote-change guard) as
  manually triggering "Save style/data to Rana" from the context menu.

## Out of Scope

- Schematisation close warning — schematisation layers have no dirty
  tracking today (deliberate, per
  `20260831-0002-schematisation-save-action.md`); extending tracking to them
  is a separate future design.
- A dedicated warning when removing individual layers from the panel —
  subsumed by the single close/quit hook; removing a layer mid-session
  triggers no prompt.
- Blocking/guaranteed-completion sync at close time (e.g. progress dialog +
  wait) — rejected in favor of fire-and-forget, to avoid a long wait after
  routine project-close/layer-removal actions.
- Distinguishing style-dirty vs. data-dirty visually (two icons) — single
  generic badge only.
- Exact dialog widget choice (`QMessageBox` vs. custom `QDialog`) and the
  specific icon asset for the badge — implementation details, left to task
  breakdown (reuse/extend `icons.py`).
