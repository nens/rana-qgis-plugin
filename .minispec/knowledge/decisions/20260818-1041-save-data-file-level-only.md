# Save-Data Restricted to File Level

**Date:** 2026-08-18
**Status:** Accepted

## Context

Vector files opened from Rana can expose multiple named layers in the
layer panel (one `QgsVectorLayer` per layer inside a gpkg, matching
`RanaLayerDataItem`). We need "save data to Rana" to work for a selection
that could be a single layer inside such a file.

The Rana file-upload API (`start_file_upload`/`finish_file_upload`) only
supports whole-file replacement — there is no endpoint for updating a
single layer inside a multi-layer file.

### Options considered

**Option A — Disable/hide per-layer "save data"**: Only offer "save data"
at the file/group level (whole file). Layer-level context menu only offers
"save style."

**Option B — Allow per-layer save data, re-upload whole file**: Clicking
"save data" on one layer silently re-uploads the entire source file,
including other layers' current on-disk state.

**Option C — Ask user each time**: Show a confirmation dialog explaining
the whole file will be re-uploaded when other layers from the same file
are also open.

## Decision

Option A — disable/hide "save data" for individual layers; only offer it
at file level.

## Reasoning

- The API genuinely cannot do a partial update — offering the action at
  layer level would misrepresent what actually happens
- Re-uploading sibling layers' state as a side effect of a seemingly
  layer-scoped action is surprising and risks silently overwriting changes
  the user didn't intend to save yet
- "Save style," by contrast, genuinely is per-layer feasible (the styles
  endpoint accepts one named file per layer), so this restriction is
  specific to data, not both actions

## Consequences

- Users saving data for a single layer's edits must use the file-level
  action, understanding it re-uploads the whole file
- No confirmation-dialog complexity (Option C) needed

## Related Decisions

- `.minispec/specs/feat_454_open_generic_files/design.md` (Phase 2)
