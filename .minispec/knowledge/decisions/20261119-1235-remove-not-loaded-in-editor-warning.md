---
type: decision
id: 20261119-1235-remove-not-loaded-in-editor-warning
date: 2026-11-19
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/utils/qgis.py
tags: [upload, save-revision, schematisation-editor]
participants: [margriet, agent]
---

# Remove "not loaded in Schematisation Editor" warning from save_revision

## Context

`Loader.save_revision` shows "The revision is not loaded in the Rana
Schematisation Editor. Continue?" when `is_loaded_in_schematisation_editor`
returns `False`. That function only checks whether the Schematisation Editor
plugin's in-memory workspace has registered the gpkg; it says nothing about
the files on disk or about unsaved edits (those are checked separately via
`QgsProject` layers).

The feature "upload local WIP revision from the file context menu" reuses
`save_revision` for a schematisation that is, by design, not opened. The
warning would fire right after the user confirmed the upload path.

## Options Considered

### Option 1: Add a flag to skip the warning for the new flow

- ✅ Layer-tree behaviour unchanged
- ❌ Keeps a check whose purpose is unclear, plus an extra parameter

### Option 2: Keep the warning for both flows

- ❌ Two consecutive confirmations in the new flow, the second always noise

### Option 3: Remove the warning entirely

- ✅ No flag, one code path
- ✅ Layer-manager flow: the group exists in the project, so the schematisation
  is open in practice; the editor workspace can lose track after a project
  reopen, which makes the warning noise rather than a safeguard
- ✅ `is_loaded_in_schematisation_editor` becomes dead code and can be deleted
- ❌ Small behaviour change in the existing layer-tree flow

## Decision

**Option 3.** Remove the warning and delete `is_loaded_in_schematisation_editor`
(sole caller was `loader.py:1046`; no tests reference it). The file-item flow
has its own confirmation dialog showing the WIP folder; an open WIP is handed
over to the opened path (`20261119-1310-hand-over-open-wip-to-opened-path`).

## Consequences

- One confirmation in the file-item flow instead of two.
- The unsaved-edits check is unchanged in behaviour; it moves to
  `commit_opened_revision` (`20261119-1250-split-commit-paths`).
