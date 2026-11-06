---
feature: feat_519_dialog
status: designed
created: 2026-11-06
decisions:
  - 20261106-1132-save-revision-scope
  - 20261106-1240-sync-prompt-dialog
  - 20261109-1100-sync-changes-model
  - 20261111-1200-sync-selection-flow
---

# Sync Selection Dialog Design

## Overview
Before any sync starts, one dialog shows what will be synced as a fully expanded tree.
Users can deselect files. A sync starts only when the user confirms, and then only for the
checked files. Both routes use the same dialog: the on-demand action from the layer panel
menu, and closing a layer or project with unsynced changes. The context menu actions are
renamed from "Save" to "Sync".

## User Stories
- As a user choosing "Sync data to Rana" on a layer group, I want to see the files and
  layers that will be uploaded, and to leave out the ones I do not want.
- As a user closing a dirty layer or project, I want to see which files have unsynced
  changes and choose whether to sync them before they are discarded.
- As a user, I want the context menu to say "Sync" like the rest of the plugin.

## Components

### Context menu (`layer_tree_menu.py`)
- "Save style to Rana" / "Save styles to Rana" becomes "Sync style to Rana" /
  "Sync styles to Rana".
- "Save data to Rana" becomes "Sync data to Rana".
- "Save revision" is unchanged (out of scope).

### Sync dialog (`layer_management/sync_prompt_dialog.py`)
`SyncDialog(parent, title, confirm_label, cancel_label, changes: SyncChanges, show_kinds=True,
project_names=None)` is the only dialog. The caller supplies the title and the button labels.
See decision `20261106-1240-sync-prompt-dialog`.

- A summary line from `build_summary`, for example
  `3 files have unsynced changes (data: 2, style: 2).`. Empty kinds are left out. A single
  file reads `1 file has unsynced changes (data and style).` With `show_kinds=False` (the
  on-demand route, which has one kind) the summary only counts files:
  `2 files have unsynced changes.`
- A header-less `QTreeWidget`, fully expanded. Tree structure:
  - Section roots "Data changes:" and "Style changes:" (only sections with changes). They are
    left out when `show_kinds=False`, so the tree then starts at the project nodes.
  - Project node with the Rana icon, showing the project name from `project_names` (project
    ID when unknown).
  - Folders with the folder icon, from `PurePosixPath(file_id).parts` without the file name.
  - File node, showing the file name, with a raster or vector icon.
  - Layer nodes under the file, showing the layer name with a geometry icon.
- Checkable: sections, projects, folders and files. Layers are display only.
  Sections, projects and folders are `ItemIsAutoTristate`, so they show a partial state.
  Files are plain checkable items. Everything starts checked.
- `selected(kind)` returns the keys of the checked files of that kind.
- The confirm button is disabled when nothing is checked.
- The tree uses the palette Base = Window role and `NoFrame`, so it blends with the dialog
  in light and dark themes.
- No `QgsCollapsibleGroupBox`, no height fitting, no details text.
- The dialog only returns the choice. It does not dispatch and it does not discard.
- Modal, run with `exec()`.

Titles and labels:

| Route | Title | Confirm | Cancel |
| --- | --- | --- | --- |
| Close, project close, layer or group removal | "Unsynced changes" | "Sync changes now" | "Continue without syncing" |
| On-demand (data) | "Sync data to Rana" | "Continue sync" | "Cancel sync" |
| On-demand (style) | "Sync style to Rana" | "Continue sync" | "Cancel sync" |

### Icons
- File: raster icon for a raster file, vector icon otherwise.
- Layer: point, linestring, polygon, table, or raster, chosen by the layer geometry.
- File and layer icons use `get_file_icon_name` and `get_icon_from_theme`. Projects use
  `rana_icon` and folders `dir_icon` from `icons.py`, as the datasource does.

### Data model (`layer_management/sync_changes.py`)
Lives next to the code that builds it, not in `utils/data_models.py`.
- `SyncKind` enum: `DATA`, `STYLE`.
- `SyncFileKey(project_id, ref)`: `ref` is the descriptor ID, or the file ID when there is no
  descriptor. It is built only by `file_key(project_id, descriptor_id, file_id)`, which returns
  `None` without a project or reference.
- `ChangedLayer(name, icon_type)` and `ChangedFile(path, icon_type, layers)`.
- `SyncChanges` frozen dataclass with `data` and `style` maps from `SyncFileKey` to
  `ChangedFile`. Helpers: `from_layers`, `files(kind)`, `for_kind(kind)`, `merge(other)`
  (returns a new object with sorted, de-duplicated layers per file), `is_empty()` and
  `file_count()`.
- `from_layers(layers, kinds, include_unknown_data=False)` reads the layers
  (`layer_sync_state`, `has_unsynced_style`) and collects only the requested kinds.
  `include_unknown_data` also counts layers whose data state is unknown, for the on-demand
  action, which is enabled for anything except clean data. Style skips layers without a
  descriptor, because they cannot be uploaded as style. A layer that is passed twice is
  counted once (by layer ID): the close route collects a file group once for each kind in
  which it is dirty.
- `project_ids()` returns the projects that have changes, for the name lookup.

### Project names (`utils/api.py`)
- `get_tenant_project(project_id)` is `GET /tenants/{tenant}/projects/{project_id}`.
- `get_project_names(project_ids) -> dict[str, str]` returns the name per project. Projects
  that fail or have no name are left out, and the dialog shows their ID. When the network is
  unavailable it stops after the first failed request, so an offline close waits for one
  request, not one per project. Names are not stored on layers, because they would go
  stale, and not read from the layer tree, because users can rename groups there.

### Callers
- On-demand (`layer_tree_menu.py`, `sync(kind, groups)`): captures the upload items for the
  kind, returns if there are none, collects `SyncChanges` for that kind, shows `SyncDialog`
  with `show_kinds=False` and the project names.
  If confirmed it keeps the upload items whose `file_key` is in `selected(kind)` and
  dispatches them. Unchecked items are dropped without discard, because live layer sources
  own nothing.
- Close and project close (`close_sync_prompt.py`, `ProjectCloseSyncPrompt` and
  `SyncPromptAction.prompt_to_sync_groups`): collects both kinds, shows `SyncDialog`, filters
  upload items by `file_key`, dispatches. Style snapshots that are not selected, and all of
  them when the user continues without syncing, go through `discard_layer_sources`.
- Layer and group removal (`LayerRemovalSyncPrompt`): accumulates changes with `merge` and
  upload items during the removal cascade, then runs the same `prompt_and_dispatch` as the
  close route after a zero-delay timer. Its cancel releases snapshots.
- The two routes keep separate filters on purpose. See decision
  `20261111-1200-sync-selection-flow`.

## Import direction
`close_sync_prompt.py` imports `LayerTreeMenuProvider` from `layer_tree_menu.py`, so
`layer_tree_menu.py` must not import `close_sync_prompt.py`. `sync_changes.py`,
`sync_summary.py` and `sync_prompt_dialog.py` depend on neither. `layer_tree_menu.py` and
`close_sync_prompt.py` both import `sync_prompt_dialog.py` and `sync_changes.py`.

## Data Model
No new persisted state. The dialog uses the per-layer dirty state already tracked by
`layer_sync_state` and `has_unsynced_style`.

## API/Interface
- `sync_changes.SyncKind`, `SyncFileKey`, `file_key`, `ChangedLayer`, `ChangedFile`,
  `SyncChanges` (`from_layers`, `files`, `for_kind`, `merge`, `is_empty`, `file_count`)
- `sync_summary.build_summary(changes, include_kinds=True) -> str`
- `sync_prompt_dialog.SyncDialog(parent, title, confirm_label, cancel_label, changes,
  show_kinds=True, project_names=None)`: `exec()`, then `selected(kind) -> set[SyncFileKey]`
- `api.get_tenant_project(project_id)`, `api.get_project_names(project_ids)`

## Removed
- `CloseSyncDialog` and `OnDemandSyncDialog` (replaced by `SyncDialog`).
- `QgsCollapsibleGroupBox` details section and height fitting.
- `build_details`, `build_sync_notice`, `format_file_changes`, `file_labels`,
  `collect_changes` (replaced by `SyncChanges.from_layers`).
- The post-dispatch "Sync started" notice. It is replaced by the pre-sync dialog.

## Out of Scope
- `save_revision`: no dialog, label unchanged.
- Changing the cancel behavior of the close prompt beyond the discard rule above.

## Open point
- `scripts/render_sync_prompt.py` is out of date: it renders the removed dialogs. It is not
  changed in this feature. Update or delete it in a follow-up.

## Testing
- Unit tests (`tests/layer_management/test_sync_changes.py`): `from_layers` (keys, file and
  layer icon types, style skipped without descriptor, `include_unknown_data`, only requested
  kinds), `merge` returns a new object with the union, `for_kind`, `is_empty`, `file_count`,
  `file_key`, `project_ids`, and a layer passed twice is counted once.
- Unit tests (`test_sync_changes.py`): upload item keys match the tree rows (the
  most important check: a mismatch would silently drop a file).
- Unit tests (`test_sync_dialog.py`, offscreen): all checked by default; unchecking a file
  removes it from `selected(kind)`; unchecking a folder unchecks its files; parent partial
  state; confirm disabled when nothing is checked; tree nesting; layers not checkable;
  no section roots with `show_kinds=False`; project name shown.
- Unit tests (`tests/utils/test_api_project_names.py`): names per project, failures left
  out, stops after a network failure.
- Unit tests (`test_sync_summary.py`): `build_summary` for data only, style only, both,
  single file, many files, counts per project, and without kinds.
- Unit tests: the project-close prompt dispatches only checked files and releases unchecked
  and cancelled style snapshots (`test_project_close_sync_prompt.py`). The layer-removal
  prompt releases snapshots on disconnect (`test_layer_removal_sync_prompt.py`).
- Gap: the on-demand `sync(kind)` route has no unit test yet. It is covered only by E2E.
- E2E: `e2e/test_layer_sync.py` answers `SyncDialog` through its buttons ("Sync changes now",
  "Continue without syncing", "Continue sync"). No new E2E tests.
- Manual: see the Notes in `tasks.md`.
