# Gating provider, not selection restriction, for multi-select safety

**Date**: 2026-08-18
**Status**: Accepted
**Feature**: task_467 — Properly handle multi-select (issue #467)

## Context

The plugin uses QGIS's native browser tree, which already supports
Ctrl/Shift multi-select across projects, folders, and files with no
plugin-side restriction. None of the existing context-menu actions
(delete, rename, upload, create-folder, defined via each `QgsDataItem`
subclass's `actions()` method) account for multi-selection — they assume
exactly one selected item.

Issue #467 asks that:
- Projects cannot be multi-selected.
- Files/folders can be multi-selected, but not together with the
  project root or files root.
- By default, no action is available for multi-select; only explicitly
  whitelisted actions may be enabled for multi-select in the future.
- For now, nothing should be enabled for multi-select at all.

## Decision

Do not attempt to prevent the native tree widget from visually allowing
an invalid multi-select (e.g. highlighting two projects at once). Doing
so would require hooking into QGIS's internal browser tree view/selection
model, which the plugin doesn't own and isn't exposed via stable public
API — fragile across QGIS versions for little practical benefit, since
nothing is actionable for invalid selections anyway.

Instead, add a single new `QgsDataItemGuiProvider`
(`RanaDataItemGuiProvider`) that gates context-menu construction. Verified
against the installed QGIS API: `populateContextMenu(self, item, menu,
selectedItems, context)` receives `selectedItems` directly as a
parameter — an iterable of ALL currently-selected items in the browser
view — so full-selection visibility is available exactly as assumed:

- 0–1 selected items: unchanged behavior (existing `actions()` menus).
- 2+ items where the selection includes any project, the files-root item,
  or otherwise doesn't qualify: the context menu is cleared (empty).
- 2+ items that are all valid files/folders (any mix of files and
  folders, no root): the context menu is built only from an explicit
  multi-select action whitelist. This whitelist starts empty, so today's
  behavior is also an empty menu, but the mechanism exists as the single,
  explicit place to enable a multi-select-capable action later.

No disabled/greyed-out actions are shown in any case — invalid or
not-yet-whitelisted actions are simply absent from the menu, rather than
present-but-disabled.

Existing per-item `actions()` methods are unchanged; the new provider is
purely additive gating logic that runs alongside them.

## Rationale

- Matches the issue literally: "for now, don't activate anything on
  multi-select" — an empty menu is the most direct way to guarantee that.
- Avoids fragile, private-API dependent code to restrict native tree
  selection, which QGIS doesn't provide a public hook for.
- Keeps the change minimal — one new file/class, zero changes to existing
  action implementations (delete, rename, upload, etc.).
- Establishes the explicit whitelist mechanism the issue calls for
  ("only specific actions can be used with multi-select, this is
  explicit") as a natural extension point for future work, without
  building any actions now.

## Alternatives Considered

1. **Hook `selectionChanged` on the browser tree and programmatically
   deselect invalid combinations.** Rejected: requires reaching into
   QGIS's internal widget tree (not a stable public API), and is
   unnecessary since gating the context menu already makes invalid
   selections inert.
2. **Show the context menu with all actions present but disabled for
   multi-select.** Rejected in favor of simply omitting actions from the
   menu — cleaner UI, and matches the "explicit whitelist" framing better
   than a set of always-disabled items.
3. **Collapse to one rule: any 2+ selection gets an empty menu, no
   distinction between valid/invalid.** Considered simplest, but rejected
   because it would require touching this again to add the whitelist
   mechanism later; keeping the valid/invalid distinction now costs little
   extra and sets up the explicit whitelist point the issue asks for.

## Open Questions (carried into implementation)

- Whether other registered `QgsDataItemGuiProvider`s could re-add entries
  to the same menu after ours clears it — worth a quick sanity check
  during implementation, but unlikely to matter for Rana's own item
  types.
