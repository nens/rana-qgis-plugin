---
type: decision
id: 20261119-1345-group-helpers-in-layer-manager
date: 2026-11-19
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/layer_manager.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
  - rana_qgis_plugin/loader.py
tags: [upload, layer-groups, module-structure]
participants: [margriet, agent]
---

# Put schematisation group helpers in layer_manager.py

## Context

`20261119-1310-hand-over-open-wip-to-opened-path` needs two helpers, one for
`commit_stored_revision` and one for `commit_opened_revision`:

- `find_schematisation_group(db_filepath)`: find the layer group whose
  `rana/schematisation_db_filepath` matches a gpkg (normalized path comparison).

`loader.py` already imports from `layer_manager.py` but not from
`layer_tree_menu.py` (a QGIS menu provider, imported by `rana_qgis_plugin.py` and
`close_sync_prompt.py`, and handed `loader` as a parameter).
`layer_tree_menu.py` already imports the group keys from `layer_manager.py`.

## Options Considered

### Option A: `layer_manager.py`

- ✅ No new import edge; matches existing dependency direction
- ✅ Group properties are written (`layer_manager.py:640-648`) and read/updated
  in the same module
- ❌ Large file (legacy classes plus new functions)

### Option B: `layer_tree_menu.py`

- ✅ Next to the lock key and menu code
- ❌ `loader.py` would import a UI module that is handed `loader`: cycle risk

### Option C: new module

- ✅ Focused, easy to test
- ❌ One more file for two small functions

## Decision

**Option A.** Both helpers go in `layer_manager.py`.

## Consequences

- `layer_tree_menu.save_revision` is reduced to a call to
  `loader.commit_opened_revision(group, parent)`, which uses both helpers'
  outputs (the group, and the revision-number update).
- `_GROUP_LOCKED_KEY` is removed rather than moved, see
  `20261119-1430-schematisation-upload-lock`.
- Helpers can be unit tested against a `QgsLayerTree` without the menu provider.
