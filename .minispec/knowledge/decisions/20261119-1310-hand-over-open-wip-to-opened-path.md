---
type: decision
id: 20261119-1310-hand-over-open-wip-to-opened-path
date: 2026-11-19
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/layer_management/layer_manager.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
tags: [upload, local-wip, layer-groups]
participants: [margriet, agent]
---

# Hand over an open WIP to the opened-revision path

## Context

`commit_stored_revision` uploads a local WIP from the file browser. The WIP may
nevertheless be open in QGIS. Opened revisions have a layer group tagged with
`rana/schematisation_id`, `rana/revision_number` and
`rana/schematisation_db_filepath` (`layer_manager.py:640-648`). Today only
`layer_tree_menu.save_revision` updates `rana/revision_number` after a
successful upload. If the browser flow uploaded an open WIP without this, the
group's revision number would go stale and a later "Save revision" from the
layer tree would use the wrong parent revision. Unsaved layer edits would also
be silently left out.

## Options Considered

### Option A: Message only

Find the group, add a sentence that unsaved changes are not included, upload the
disk state.

- ✅ Smallest change
- ❌ Stale revision number remains
- ❌ User can only be told about excluded edits, not offered to save them

### Option B: Hand over to the opened path when a group exists

After path confirmation, look for a group whose
`rana/schematisation_db_filepath` matches the WIP gpkg. If found, call
`commit_opened_revision(group, parent)` (unsaved-edits prompt, revision-number
update); otherwise call `save_revision` directly.

- ✅ Browser upload behaves like layer-tree upload
- ✅ Fixes stale revision number
- ✅ The confirm dialog needs no "unsaved changes" sentence
- ❌ Revision-number update moves out of `layer_tree_menu.save_revision` into a
  shared helper; new group-lookup function
- ❌ Two sequential dialogs when the WIP is open with unsaved edits

## Decision

**Option B.**

## Consequences

- New function to find the layer group for a gpkg path (normalized path match on
  `rana/schematisation_db_filepath`), placed in `layer_manager.py`.
- The revision-number update becomes a helper called by
  `commit_opened_revision`, which both entry points reach for an open WIP.
- When the group is opened from the stored path, the group's
  `rana/revision_number` is used (same as the layer panel), not
  `wip_revision.number`.
- Concurrent uploads are prevented separately, see
  `20261119-1430-schematisation-upload-lock`.
