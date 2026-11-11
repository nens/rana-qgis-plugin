---
type: decision
id: 20261111-1200-sync-selection-flow
date: 2026-11-11
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/sync_prompt_dialog.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
  - rana_qgis_plugin/layer_management/close_sync_prompt.py
tags: [sync, ui, lifecycle]
participants: [engineer, build agent]
---

# The Sync Dialog Returns A Choice And The Callers Act On It

## Context
The sync dialog lets the user deselect files before a sync. Something must then decide what
happens to the unselected files. Two routes use the dialog, and they own their upload inputs
differently. A live layer source owns nothing. A style snapshot owns a temporary directory
that must be removed.

## Decision
- The dialog only returns the user's choice: `selected(kind)` gives the checked file keys.
  It does not dispatch and does not discard. The caller acts on the result.
- Callers filter the upload items by `file_key` and dispatch only those whose key is selected.
- On-demand (`layer_tree_menu.py`): unselected items are dropped without discard, because the
  sources are live layers that own nothing.
- Close and project close (`close_sync_prompt.py`): unselected style snapshots go through
  `discard_layer_sources`. So do all of them when the user continues without syncing, and
  on cancel, because the snapshots own temporary directories.
- The two routes keep separate filters on purpose. A shared helper would hide the discard
  difference, and the on-demand route has no snapshots to release.

## Alternatives Considered
- The dialog discards unselected items itself: rejected. The dialog would need to know which
  routes own snapshots, which couples it to the upload pipeline.
- One shared filter and discard for both routes: rejected. On-demand would call discard on
  live sources for no reason, and the close route's cancel rule would be lost in the
  generic code.
- Dispatching all items and letting the upload skip unselected ones: rejected. It would
  start work the user declined and make cancel unreliable.

## Consequences
- A discard bug can only be in the close route, which has tests for cancel and unchecked
  snapshots in `tests/layer_management/test_project_close_sync_prompt.py`.
- The on-demand route has a unit test for dispatching only the selected items
  (`tests/layer_management/test_layer_tree_menu_sync.py`). Cancel is covered only by E2E.
