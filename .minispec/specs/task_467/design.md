---
feature: multi-select-handling
status: implemented
created: 2026-08-18
decisions:
  - 20260818-1300-gating-provider-not-selection-restriction
---

# Properly Handle Multi-Select Design

Issue: https://github.com/nens/rana-qgis-plugin/issues/467

## Overview

QGIS's native browser tree already allows Ctrl/Shift multi-select across
projects, folders, and files, but nothing in the plugin accounts for it.
Every existing context-menu action (delete, rename, upload, create-folder)
assumes exactly one selected item, and would behave incorrectly or
confusingly if invoked while multiple items are selected.

This feature does not implement any new multi-select actions. It makes
multi-select *safe*: no action can be invoked on an invalid or
not-yet-supported multi-selection. A single new `QgsDataItemGuiProvider`
gates context-menu construction based on the full current selection.

## Scope

**In scope:**
- Prevent any context-menu action from firing on multi-selections that
  include projects, mixed item types, or the files-root item.
- Prevent any context-menu action from firing on valid multi-selections
  (files/folders only, no root) until actions are explicitly whitelisted.
- Establish the extension point (whitelist) for adding multi-select-safe
  actions later.

**Out of scope (future work):**
- Actually enabling any action for multi-select (e.g. multi-delete).
- Preventing the native tree widget from visually highlighting an invalid
  multi-selection (e.g. two projects highlighted at once). Visually it can
  still happen; it's just guaranteed inert.

## Behavior

Single source of truth: `RanaDataItemGuiProvider.populateContextMenu()`,
called by QGIS whenever a context menu is being built, with a
`QgsDataItemGuiContext` giving access to `selectedItems()`.

| Selection | Menu shown |
|---|---|
| 0 or 1 items | Unchanged — existing per-item `actions()` list applies. |
| 2+ items, includes any `RanaProjectDataItem` | Empty (menu cleared). |
| 2+ items, includes `RanaFilesDataItem` (files root) | Empty (menu cleared). |
| 2+ items, all `RanaFolderDataItem`/`RanaFileDataItem` (any mix of files and folders), none root | Built from an explicit multi-select action whitelist (currently empty — menu is empty in practice, but the mechanism exists). |

No disabled/greyed-out menu items are shown in any case — if an action
isn't valid/whitelisted for the current selection, it's simply absent from
the menu.

## Components

### `RanaDataItemGuiProvider` (new)

New file, e.g. `data_items/gui_provider.py`. Registered once via
`QgsGui.dataItemGuiProviderRegistry().addProvider(...)` at plugin load
(alongside existing provider registration in `rana_qgis_plugin.py`).

Responsibilities:
- Implements
  `populateContextMenu(self, item, menu, selectedItems, context)` —
  confirmed against the installed QGIS API: `selectedItems` is passed
  directly as a parameter (an iterable of ALL currently-selected
  `QgsDataItem`s in the browser view), not derived from `context`. QGIS
  calls this once per registered `QgsDataItemGuiProvider`; each provider
  is responsible for inspecting `item`/`selectedItems` itself and adding
  or removing menu entries as appropriate. The base implementation does
  nothing and does not clear prior entries, so our provider must
  explicitly call `menu.clear()` when gating out an invalid/ungated
  selection.
- Classifies the selection:
  - `len(selectedItems) <= 1` → no-op, let default `actions()`-based menu
    stand.
  - Otherwise, determine validity per the table above.
  - If invalid → `menu.clear()`.
  - If valid → `menu.clear()` then rebuild from only whitelisted
    multi-select actions (see below); currently none, so menu ends up
    empty.

### Multi-select action whitelist (new, minimal)

A small, explicit list/set (e.g. in `file_actions.py` or the new gui
provider module) naming which `FileAction` values are permitted for
multi-select. Starts empty. Adding an action here is the single place
future work touches to enable a new multi-select-capable action.

## Data Model

No new persisted data. No changes to `RanaProjectDataItem`,
`RanaFolderDataItem`, `RanaFileDataItem`, or `Loader`.

## Open Questions

- Whether other registered `QgsDataItemGuiProvider`s (if any exist
  elsewhere, e.g. QGIS core providers for generic items) could re-add
  entries to the same menu after ours clears it — needs a quick check
  during implementation, but is unlikely to matter for Rana-specific item
  types.
