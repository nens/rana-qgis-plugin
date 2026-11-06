---
feature: feat_454_dialog
status: implemented
created: 2026-11-06
decisions:
  - 20261106-1132-sync-notice-tense
  - 20261106-1132-save-revision-scope
  - 20261106-1240-sync-prompt-dialog
  - 20261109-1100-sync-changes-model
---

# Sync Change Summary Design

## Overview
Make sync messages say what is being synced. Both the on-demand notice and the close and
project-close prompt use the same dialog: a short summary line and a collapsible "More
details" section listing the changed layers per file. Each sync action moves one kind of
change (data or style), so the on-demand notice has a single section. The close prompt
has data and style sections. The context menu actions are renamed from "Save" to "Sync".

## User Stories
- As a user choosing "Sync data to Rana" on a layer group, I want a notice that
  mentions only data, with the files and layers involved available under "More details".
- As a user closing a dirty layer or project, I want a short summary of how many files
  changed and how, and the option to see which layers changed.
- As a user, I want the context menu to say "Sync" like the rest of the plugin.

## Components

### Context menu (`layer_tree_menu.py`)
- "Save style to Rana" / "Save styles to Rana" becomes "Sync style to Rana" /
  "Sync styles to Rana".
- "Save data to Rana" becomes "Sync data to Rana".
- "Save revision" is unchanged (out of scope).

### Sync dialogs (`layer_management/sync_prompt_dialog.py`, new)
`SyncPromptDialog` is the base `QDialog`. Subclasses only supply the title, the summary
and the buttons. See decision `20261106-1240-sync-prompt-dialog`.

Base class (`SyncPromptDialog(parent, title, summary_html, changes: SyncChanges)`):
- Summary line (always visible).
- A `QgsCollapsibleGroupBox` titled "More details", collapsed by default in both dialogs
  (set once in the base class, not overridden).
- Details area: a `QScrollArea` with auto scrollbars (shown only when needed). Its content
  is `build_details(changes)`.
- A resizable, movable window. Expanding or collapsing the details resizes the height to
  fit the contents: at least the default height, at most what the capped details area needs.
- A button row that subclasses fill.

`CloseSyncDialog(parent, changes)`:
- Title "Unsynced changes". Summary from `build_summary`, for example
  `3 files have unsynced changes (data: 2, style: 2).` Empty kinds are left out. A single
  file reads `1 file has unsynced changes (data and style).`
- Buttons "Sync now" and "Continue without syncing". Modal, run with `exec()`.
  `selected_label()` returns the clicked button label. The dialog is not deleted on close,
  because the caller reads the result after `exec()` returns.

`OnDemandSyncDialog(parent, kind: SyncKind, changes)`:
- Title "Sync started". One kind only, so only that section is filled.
- Summary from `build_sync_notice`:
  - One file: `Syncing data of <b>name.gpkg</b> to Rana...`
  - Several files: `Syncing data of 5 files to Rana...` (the files are under "More details")
- One "OK" button. Not modal: shown with `show()`. It stays open until the user dismisses
  it (no auto-close). Several can be open at once; no de-duplication. Shown after dispatch,
  never blocks or cancels it. It is parented to the main window and deletes itself on close
  (`WA_DeleteOnClose`), so nothing tracks it.

Details content (rich text, in a `QLabel` inside the scroll area): a bold section heading
("Data changes:", "Style changes:") above a bullet list of files. A file with one changed
layer reads `file: layer`. A file with several changed layers has a nested bullet list of
layers. Sections are omitted when empty, there is no truncation, and a file appears once per
section it has changes in.

### Change model (`utils/data_models.py`)
No QGIS imports, so the formatting module can use it.
- `SyncKind` enum: `DATA`, `STYLE`.
- `SyncChanges` frozen dataclass: `data` and `style` map file name to sorted changed layer
  names. `files(kind)`, `for_kind(kind)`, `is_empty()` and `file_count()` are helpers;
  `merge(other)` returns a new object.

### Collecting changes (`layer_management/sync_changes.py`)
- `collect_changes(layers, kinds, include_unknown_data=False) -> SyncChanges` reads names
  from the layers (`layer_sync_state` and `has_unsynced_style`), not from the upload items,
  and collects only the requested kinds. The upload items keep one entry per file and are
  used for dispatch only.
- `include_unknown_data` also counts layers whose data state is unknown. The on-demand sync
  passes it, because the "Sync data to Rana" action is enabled for any state except clean.
- The deferred layer-removal prompt accumulates a `SyncChanges` with `merge` and resets it
  to `SyncChanges()` after the prompt.
- Takes layers, not groups, so it does not import `layer_tree_menu.py`. Callers get the
  layers from `LayerTreeMenuProvider.collect_all_layers`.

### Close and project-close prompt (`close_sync_prompt.py`)
- Collects the changes with `collect_changes` (both kinds), then opens `CloseSyncDialog`.

### On-demand sync (`layer_tree_menu.py`, `sync(kind)`)
- One helper for both kinds. It captures the upload items for the kind and returns if there
  are none. It then collects `SyncChanges` for that kind, dispatches, and shows
  `OnDemandSyncDialog`.

### Formatting (`layer_management/sync_summary.py`)
Pure text formatting, no QGIS imports: `build_summary`, `build_details`,
`format_file_changes`, `build_sync_notice`.

## Import direction
`close_sync_prompt.py` imports `LayerTreeMenuProvider` from `layer_tree_menu.py`, so
`layer_tree_menu.py` must not import `close_sync_prompt.py`. `sync_changes.py`,
`sync_summary.py` and `sync_prompt_dialog.py` depend on neither. They share the types in
`utils/data_models.py`. `layer_tree_menu.py` imports all three.

## Data Model
No new persisted state. The prompt uses per-layer dirty state already tracked by
`layer_sync_state` and `has_unsynced_style`.

## API/Interface
- `data_models.SyncKind`, `data_models.SyncChanges`
- `sync_changes.collect_changes(layers, kinds, include_unknown_data=False) -> SyncChanges`
- `sync_summary.build_summary(changes) -> str`
- `sync_summary.build_details(changes) -> str`
- `sync_summary.build_sync_notice(kind, changes) -> str`
- `sync_prompt_dialog.CloseSyncDialog(parent, changes)`: `exec()`, then `selected_label()`
- `sync_prompt_dialog.OnDemandSyncDialog(parent, kind, changes)`: `show()`

## Out of Scope
- `save_revision`: no notice, label unchanged.
- Changing the cancel behavior of the close prompt.

## Testing
- Unit tests: `build_summary` (data only, style only, both, single file, many files).
- Unit tests: `build_details` (empty section omitted, file in both sections, many layers).
- Unit tests: `build_sync_notice` for data and style, single and several files.
- Unit tests: `SyncChanges` (`merge` returns a new object, `for_kind`, `is_empty`,
  `file_count`) and `collect_changes`, including `kinds` and `include_unknown_data`.
- Unit tests: the deferred layer-removal prompt merges changes across removals.
- Unit tests: both dialogs (details collapsed by default, buttons, summary text, height
  fit, on-demand dialog is non-blocking and closes with OK).
- E2E: `e2e/test_layer_sync.py` answers the close dialogs and dismisses the on-demand
  notice through the dialog buttons.
- Manual: context menu shows "Sync data/style to Rana". The on-demand dialog names only
  the chosen kind, does not block, and "More details" lists the files and layers. Closing
  a dirty layer or project opens the dialog; "More details" opens and closes, and the
  scrollbar appears only with long lists. The dialog can be moved and resized.
