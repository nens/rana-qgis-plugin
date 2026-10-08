# Local-Session Rename/Delete Linking Reuses Loader Signals

**Date:** 2026-08-18
**Status:** Accepted

## Context

Files/folders can be renamed or deleted through this same QGIS session's
Browser tree, via `Loader.rename_item()`/`Loader.delete_file()`, which
already emit `item_renamed(old_path, new_path, is_folder)` and
`item_deleted(path, is_folder)` (see
`.minispec/knowledge/decisions/20260814-1001-loader-mutation-methods-and-signals.md`),
with a documented prefix-based path remapping contract for subscribers
(`.minispec/knowledge/decisions/20260814-1002-prefix-based-path-remapping-contract.md`)
that explicitly anticipated a future layer-panel subscriber.

## Decision

A new lightweight listener subscribes to these existing signals rather
than introducing a new signal path. On rename, it applies the documented
prefix-remap rule to each rana-linked layer's stored `file_path`. On
delete, it clears rana refs for layers whose stored `file_path` starts
with the deleted path. In neither case is the layer's display name or its
layer-tree group names changed — only the stored reference is updated
or cleared.

## Reasoning

- This signal contract was explicitly designed with this future subscriber
  in mind — implementing anything else would duplicate work and diverge
  from the documented contract
- Prefix matching correctly handles the direct-file-rename, ancestor-
  folder-rename, and layer-inside-renamed-file cases uniformly, exactly as
  the original contract intended

## Consequences

- Only covers changes made through this session's own Loader — changes
  made remotely (another user/session) are not observable this way; see
  the separate remote-change-guard decision
  (`20260818-1041-remote-change-lazy-guard.md`) for that case

## Related Decisions

- `.minispec/knowledge/decisions/20260814-1001-loader-mutation-methods-and-signals.md`
- `.minispec/knowledge/decisions/20260814-1002-prefix-based-path-remapping-contract.md`
- `20260818-1041-remote-change-lazy-guard.md`
- `.minispec/specs/feat_454_open_generic_files/design.md` (Phase 3a)
