# Decision: Use context-menu dialog for rename, not QgsDataItemGuiProvider

**Date:** 2026-08-17
**Status:** Accepted
**Supersedes:** [20260814-1000-rename-via-gui-provider](20260814-1000-rename-via-gui-provider.md)

## Context

`20260814-1000` chose `QgsDataItemGuiProvider.rename()` for native inline
rename (F2 / slow double-click), to avoid the deprecated `QgsDataItem.rename()`
API. Implementing `feat_451_with_tasks` surfaced two problems with that
approach:

- Inline editing intercepts F2/Enter keyboard events in ways that conflict
  with QGIS's own event handling, causing intermittent side effects.
- Rename is moving onto an asynchronous Loader-owned lifecycle (see
  `20260814-1001`, updated below). Native inline rename has no natural place
  to show pending/in-progress/error state while a background request is in
  flight; a dialog does.

## Decision

Remove `RanaDataItemGuiProvider` and the `Rename` item capability. Wire the
existing context-menu `Rename` `QAction` to an explicit dialog
(`QInputDialog`-style), consistent with how `Delete` and `Create directory`
are already triggered. On confirmation, submit the rename through the async
Loader lifecycle (`20260814-1001`, as amended).

## Reasoning

- A dialog gives an explicit confirm/cancel step and a natural place to
  disable/show progress while the async operation runs; native inline
  rename does not.
- Removes the F2/Enter keyboard-event conflict entirely by not using inline
  editing.
- Consistent with the `actions()`-based context-menu pattern already used for
  Delete and Create directory — one less UI pattern in the codebase.
- The original concern in `20260814-1000` (avoiding deprecated
  `QgsDataItem.rename()`) is moot either way, since neither this option nor
  the GUI-provider option uses that deprecated API.

## Risks

- Users lose the native F2/inline-rename affordance; this is an accepted UX
  tradeoff for reliability and consistency with other actions.
- `RanaDataItemGuiProvider` registration/unregistration in plugin lifecycle
  must be cleanly removed to avoid stale references across plugin reloads.
