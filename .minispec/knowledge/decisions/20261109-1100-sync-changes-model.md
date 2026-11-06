---
type: decision
id: 20261109-1100-sync-changes-model
date: 2026-11-09
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/data_models.py
  - rana_qgis_plugin/layer_management/sync_changes.py
  - rana_qgis_plugin/layer_management/sync_summary.py
  - rana_qgis_plugin/layer_management/sync_prompt_dialog.py
  - rana_qgis_plugin/layer_management/close_sync_prompt.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
tags: [sync, messaging]
participants: [engineer, build agent]
---

# Sync Changes Are Read From Layers And Typed

## Context
The sync dialogs list changed layers per file. The upload items used for dispatch hold one
entry per file, so they cannot name the layers. The summary, the dialogs, the on-demand
action and the deferred layer-removal prompt all need the same data.

## Decision
- Read the changed layer names from the layers (`layer_sync_state`, `has_unsynced_style`),
  not from the upload items. The upload items are used for dispatch only.
- `SyncKind` (`DATA`, `STYLE`) and the frozen `SyncChanges` dataclass (`data` and `style`:
  file name to sorted layer names) live in `utils/data_models.py`, so the formatting
  module can use them without QGIS imports. `merge` returns a new object.
- `collect_changes(layers, kinds, include_unknown_data=False)` takes layers, so it does not
  import `layer_tree_menu.py`, and collects only the requested kinds. The on-demand sync
  passes `include_unknown_data=True`, because its action is enabled for any state except
  clean; the close routes only count layers that are dirty.
- One `sync(kind, groups)` helper in `layer_tree_menu.py` serves both on-demand actions.
- The on-demand dialog is parented to the main window and deletes itself on close.
  `CloseSyncDialog` does not, because the caller reads its result after `exec()`.

## Alternatives Considered
- Plain strings and `(data, style)` tuples: rejected. Errors would show up only at runtime
  and a tuple invites in-place mutation.
- Collecting both kinds and discarding one for on-demand: rejected as wasted work.

## Consequences
- The upload items and the changes are two views of the same groups. They are captured
  together, because on the close routes the layers are gone by the time the user answers.
- `include_unknown_data` mirrors the menu's enablement rule. If that rule changes, update
  both.
