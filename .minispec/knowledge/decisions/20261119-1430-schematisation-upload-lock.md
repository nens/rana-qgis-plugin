---
type: decision
id: 20261119-1430-schematisation-upload-lock
date: 2026-11-19
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/layer_management/layer_manager.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
tags: [upload, save-revision, locking, local-wip]
participants: [margriet, agent]
---

# One revision upload per schematisation at a time, tracked by the loader

## Context

Today a revision upload is blocked only through the layer group property
`rana/schematisation_uploading` (`_GROUP_LOCKED_KEY`), which disables "Save
revision" in the layer panel. With the new "Upload local revision" file action,
an upload can start for a schematisation that is not open (no group), or for an
open one from outside the layer panel. Two uploads of the same WIP could then run
at the same time.

The group property is also written to the project file. If QGIS stops during an
upload, the group stays locked after reopening the project.

## Options Considered

### Option A: Keep the group property and check it from the file action too

- ❌ No protection when the schematisation is not open
- ❌ Stale lock persisted in the project file

### Option B: In-memory set of schematisation ids on `Loader`

- ✅ Covers both entry points, open or not
- ✅ Not persisted; cannot go stale across sessions
- ✅ Removes `_GROUP_LOCKED_KEY` and the lock/unlock wiring on the group

## Decision

**Option B.**

- `Loader` keeps a set of schematisation ids whose revision upload task is
  running, with `is_revision_upload_in_progress(schematisation_id) -> bool`.
- `save_revision` adds the id when it starts the `SchematisationUploadTask` and
  removes it on `taskCompleted` / `taskTerminated` (the terminal `QgsTask`
  signals, always emitted). It refuses to start when the id is already in the
  set (safety net).
- `commit_opened_revision` and `commit_stored_revision` check the lock before any
  dialog and show "A revision of this schematisation is already being uploaded.
  Wait until it has finished." when locked.
- The layer panel keeps "Save revision" disabled while locked, now based on
  `loader.is_revision_upload_in_progress(...)` instead of the group property.
- `save_initial_revision` does not take the lock: during the first upload there is
  no item from which another revision can be committed.

## Consequences

- `_GROUP_LOCKED_KEY` and the `rana/schematisation_uploading` property are
  removed. Old project files may still contain the property; it is ignored.
- The group helper shrinks to updating `rana/revision_number` after a successful
  upload.
