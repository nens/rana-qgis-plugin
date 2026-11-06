---
type: decision
id: 20261106-1240-sync-prompt-dialog
date: 2026-11-06
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/sync_prompt_dialog.py
  - rana_qgis_plugin/layer_management/close_sync_prompt.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
  - rana_qgis_plugin/layer_management/sync_summary.py
tags: [sync, messaging, ui]
participants: [engineer, build agent]
---

# One Tree Dialog Shown Before Any Sync

## Context
Users should see what a sync moves before it starts, on both routes: the on-demand sync
from the layer panel menu and the close, project-close and layer-removal prompts. Each
route used to have its own dialog, with a collapsed "More details" section. That hid the
files the user was about to sync, and a collapsed box made it hard to deselect anything.
The user needs to see the files, and to decide which ones are synced.

## Options Considered
- **`QMessageBox.setDetailedText()`:** rejected. The toggle label is fixed, and the text is
  plain, so the sections cannot be bold.
- **Keep the collapsible details with a notice after dispatch:** rejected. The files are
  hidden, the user cannot deselect them, and the sync has already started.
- **Two dialog classes (close and on-demand):** rejected. Wording and behavior drift apart,
  and the on-demand one needed a non-blocking notice that cannot offer a choice.
- **Dialog that dispatches or discards itself:** rejected. See
  `20261111-1200-sync-selection-flow`.
- **`QgsCollapsibleGroupBox` plus height fitting:** rejected as more code for the same
  view. A fully expanded tree shows the same information with checkboxes.

## Decision
- `SyncDialog(parent, title, confirm_label, cancel_label, changes, show_kinds=True,
  project_names=None)` is the only sync dialog. The caller passes the title and the labels.
- The dialog is a header-less `QTreeWidget`, fully expanded. Sections are "Data changes:"
  and "Style changes:", then the project, the folders, the file, and the layers. The
  on-demand route has a single kind, so it passes `show_kinds=False`: the section roots are
  left out and the summary only counts files.
- The project node shows the project name. The callers fetch it with
  `api.get_project_names` (`GET .../projects/{id}`, one small request per project) and the
  dialog falls back to the project ID. Names are not stored on layers, because they go
  stale, and not read from the layer tree, because users can rename groups there.
- Sections, projects, folders and files are checkable. Sections, projects and folders are
  auto-tristate. Files are plain checkable. Layers are display only. Everything starts
  checked.
- The dialog is modal and returns only the choice. `selected(kind)` gives the checked file
  keys. The caller dispatches. The dialog does not dispatch or discard.
- Labels: close "Unsynced changes", "Sync changes now", "Continue without syncing".
  On-demand "Sync data to Rana" or "Sync style to Rana", "Continue sync", "Cancel sync".
- The summary line comes from `build_summary`, for example
  `3 files have unsynced changes (data: 2, style: 2).` Without kinds it reads
  `2 files have unsynced changes.`

## Consequences
- The project name lookup is a synchronous request before the dialog opens. It has the
  network timeout, and `get_project_names` stops after the first network failure, so an
  offline close adds at most one wait. A failed lookup shows the project ID.
- `CloseSyncDialog`, `OnDemandSyncDialog`, `QgsCollapsibleGroupBox`, height fitting, the
  details formatter and the post-dispatch notice are removed.
- The on-demand sync is now modal. It waits for the user before it dispatches, so its
  E2E test answers the dialog.
- Capture must record every dirty layer per file, not one name per file item; see
  `20261109-1100-sync-changes-model`.
- The tree needs a palette Base of Window and `NoFrame`, so it matches the dialog in light
  and dark themes.
