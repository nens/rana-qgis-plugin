# Sync-In-Progress Lock via Central Registry

**Date:** 2026-08-18
**Status:** Accepted

## Context

Save-style/save-data actions run as background `SyncTask(QgsTask)`
instances. We need to prevent a second save being started for the same
layer/file while one is already in flight, per the original requirement
that new saves for the same items should be blocked while syncing.

### Options considered

**Option A — central registry keyed by the canonical Rana file reference**:
Register a file when a `SyncTask` starts and remove it when the task finishes.
The layer-tree context-menu provider checks the registry and disables actions
for layers/groups referring to a locked file. A derived
`rana/sync_in_progress` customProperty may be maintained for display.

**Option B — In-memory registry of in-flight layer/file ids**: A
process-local set of ids currently syncing, checked by the menu provider.

## Decision

Option B — central registry keyed by the canonical Rana file reference,
with any customProperty used only as derived display state. This prevents
concurrent saves across distinct layer/group items referencing the same file.

## Reasoning

- Coordinates locks at file scope, matching the upload API's replacement
  semantics even when multiple layer/group items reference one file.
- Keeps persistent references in custom properties while treating transient
  lock state as process-local.
- The registry must release locks on task completion, failure, and
  cancellation; plugin unload should clear any remaining entries.

## Consequences

- If QGIS crashes mid-sync, in-memory locks disappear with the process. A
  saved derived customProperty may remain stale, so it must not be used as
  the lock source-of-truth; clear or refresh it on project load if displayed.

## Related Decisions

- `20260818-1041-rana-layer-reference-storage.md`
- `.minispec/specs/feat_454_open_generic_files/design.md` (Phase 2)
