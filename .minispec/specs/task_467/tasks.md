---
feature: task_467-multi-select
status: complete
created: 2026-08-18
chunk_size: adaptive
total_tasks: 4
estimated_lines: ~180
---

# Properly Handle Multi-Select Tasks

Design: `.minispec/specs/task_467/design.md`
Decision: `.minispec/knowledge/decisions/20260818-1300-gating-provider-not-selection-restriction.md`

## Overview

Implements multi-select safety for the Rana browser items: a new
`RanaDataItemGuiProvider` gates context-menu construction so no action can
ever fire on an invalid multi-selection (projects, mixed with the
files-root, etc.), and valid multi-selections (files/folders only, no
root) get an empty menu until actions are explicitly whitelisted in the
future. No existing action code changes.

## Task List

### Foundation

#### Task 1: Selection classification helpers
- **Estimate:** ~40-60 lines incl. tests
- **Files:** `rana_qgis_plugin/data_items/gui_provider.py` (new),
  `tests/data_items/test_gui_provider.py` (new)
- **Description:** Pure function(s) classifying a selection of
  `QgsDataItem`s into: single item (no gating), invalid multi-select
  (contains a `RanaProjectDataItem`, a `RanaFilesDataItem`/root, or is
  otherwise disallowed), or valid multi-select (any mix of
  `RanaFolderDataItem`/`RanaFileDataItem`, no root). Lives directly in the
  new module — not split further, per the constitution's conservative
  abstraction threshold.
- **Depends on:** None
- **Acceptance:** unit tests cover — single item, 2 files, file+folder
  mix, 2 projects, project+file mix, folder-root included, files-root
  included.
- **Evidence:** `pytest tests/data_items/test_gui_provider.py` passes.

### Core Implementation

#### Task 2: `RanaDataItemGuiProvider.populateContextMenu`
- **Estimate:** ~40-60 lines incl. tests
- **Files:** `rana_qgis_plugin/data_items/gui_provider.py`,
  `tests/data_items/test_gui_provider.py`
- **Description:** Implements `id()` and
  `populateContextMenu(item, menu, selectedItems, context)`:
  - `len(selectedItems) <= 1` → no-op.
  - Invalid multi-select → `menu.clear()`.
  - Valid multi-select → `menu.clear()` then populate from the (currently
    empty) multi-select action whitelist.
- **Depends on:** Task 1
- **Acceptance:** tests using a mock/fake `QMenu` and lists of mock data
  items verify `clear()` is called (or not) in each scenario from the
  design's behavior table.
- **Evidence:** `pytest tests/data_items/test_gui_provider.py` passes.

#### Task 3: Register/unregister the GUI provider in the plugin
- **Estimate:** ~15-20 lines
- **Files:** `rana_qgis_plugin/rana_qgis_plugin.py`
- **Description:** Instantiate `RanaDataItemGuiProvider` in
  `RanaQgisPlugin.__init__`; register via
  `QgsGui.dataItemGuiProviderRegistry().addProvider(...)` in `initGui()`,
  unregister in `unload()` — mirrors the existing
  `dataItemProviderRegistry` registration pattern already in the file.
- **Depends on:** Task 2
- **Acceptance:** plugin loads/unloads without error.
- **Evidence:** manual smoke test in QGIS (load/unload the plugin, no
  exceptions); existing test suite still passes.

### Integration & E2E

#### Task 4: E2E test — multi-select gating in `test_files`
- **Estimate:** ~35 lines (already implemented, see below)
- **Files:** `e2e/test_datasource.py`, `e2e/test_utils.py`
- **Description:** Extends the existing `test_files` end-to-end flow,
  inserted just before the final delete assertions (after the
  `renamed_bar` rename, before deleting `foo`). Adds:
  - `build_context_menu(data_item, selected_items)` in `test_utils.py` —
    builds a context menu the way the real QGIS Browser panel does:
    `item.actions()` entries plus every registered
    `QgsDataItemGuiProvider.populateContextMenu()`. This is necessary
    because the existing `click_context_menu_action()` helper calls
    `item.actions()` directly and never exercises GUI providers, so it
    can't observe the new gating behavior.
  - A parametrized loop in `test_files` asserting an empty menu
    (`not menu.actions()`) for 4 representative multi-select cases: two
    folders, folder + file, project + folder, files-root + folder.
  - Reuses already-live items from earlier in the flow (`foo_item`,
    `baz_item`, `renamed_item`, `project_item`, `files_item`) rather than
    stale references to renamed/replaced items.
- **Depends on:** Task 3 (the provider must be registered via
  `plugin.initGui()`, which the `plugin` fixture already calls, for
  `build_context_menu` to see it in `QgsGui.dataItemGuiProviderRegistry()`)
- **Acceptance:** the 4 multi-select cases in `test_files` assert an empty
  context menu; single-select assertions elsewhere in `test_files` are
  unaffected.
- **Evidence:** `test_files` passes in the e2e suite (CI on PR; not run
  locally after every change per repo convention). Implementation
  already written — will only pass once Tasks 1-3 exist, since
  `RanaDataItemGuiProvider` isn't registered yet.

## Notes
- No disabled/greyed-out menu items are ever shown — invalid or
  not-yet-whitelisted actions are simply absent from the menu.
- Existing per-item `actions()` methods (`file_item.py`, `folder_item.py`,
  `file_actions.py`) are untouched.
- Task 4's e2e code was written ahead of Tasks 1-3 as a concrete
  executable spec for the gating behavior; it will fail until the
  provider exists and is registered.
- Deferred to future work: actually enabling any action for multi-select
  (the whitelist stays empty in this feature); preventing the native
  browser tree from visually allowing an invalid multi-select highlight
  (not needed since it's inert either way).

## Progress
- [x] Task 1: Selection classification helpers
- [x] Task 2: `RanaDataItemGuiProvider.populateContextMenu`
- [x] Task 3: Register/unregister the GUI provider in the plugin
- [x] Task 4: E2E test — multi-select gating in `test_files` (implementation it depends on is now in place)
