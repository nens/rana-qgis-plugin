---
type: decision
id: 20261109-1100-sync-changes-model
date: 2026-11-09
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/sync_changes.py
  - rana_qgis_plugin/layer_management/sync_summary.py
  - rana_qgis_plugin/layer_management/sync_prompt_dialog.py
  - rana_qgis_plugin/layer_management/close_sync_prompt.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
tags: [sync, messaging]
participants: [engineer, build agent]
---

# Sync Changes Are Read From Layers And Keyed By File

## Context
The sync dialog lists changed layers per file, and it must match each checkbox to the upload
item that dispatches the file. The upload items hold one entry per file, so they cannot name
the layers. The summary, the dialog, the on-demand action and the deferred layer-removal
prompt all need the same data, and the match between them must be exact.

## Decision
- Read the changed layers from the layers (`layer_sync_state`, `has_unsynced_style`), not from
  the upload items. The upload items are used for dispatch only.
- The file key is `SyncFileKey(project_id, ref)`. `ref` is the descriptor ID, or the file ID
  when there is no descriptor. It is built only by `file_key(project_id, descriptor_id,
  file_id)`, in `layer_management/sync_changes.py`. Both the upload items and the tree rows
  use it, so the checkbox and the dispatch cannot disagree. Without a project or a reference
  there is no key.
- `ChangedLayer(name, icon_type)` and `ChangedFile(path, icon_type, layers)` are frozen
  dataclasses in `layer_management/sync_changes.py`. They are not in `utils/data_models.py`.
  This corrects the earlier decision text, which placed them there.
- `SyncChanges` is a frozen dataclass with `data` and `style` maps from `SyncFileKey` to
  `ChangedFile`, and a `project_names` map read from the layers (see
  `20261106-1240-sync-prompt-dialog`). `from_layers(layers, kinds, include_unknown_data=False)` collects only the
  requested kinds. `merge` returns a new object with the union and sorted layers.
- The on-demand sync passes `include_unknown_data=True`, because its action is enabled for any
  state except clean. The close routes only count dirty layers.
- Style skips layers without a descriptor, because they cannot be uploaded as style.
- `from_layers` counts a layer once, by layer ID. The close route passes the layers of every
  group that is dirty for either kind, so a group dirty for both is collected twice. Without
  this, each layer showed twice in the tree. `project_ids()` lists the projects with changes
  for the name lookup.

## Alternatives Considered
- Plain strings and `(data, style)` tuples: rejected. Errors would show up only at runtime,
  and a tuple invites in-place mutation.
- Keying by file path alone: rejected. The same path in two projects would merge, so the
  project is part of the key.
- Collecting both kinds and discarding one for on-demand: rejected as wasted work.

## Consequences
- The upload items and the changes are two views of the same groups. They are captured
  together, because on the close routes the layers are gone by the time the user answers.
- `include_unknown_data` mirrors the menu's enablement rule. If that rule changes, update
  both.
- Tests in `tests/layer_management/test_sync_changes.py` check that upload item keys match
  tree rows. A change to either side that breaks the match fails there.
