# Remote-Change Detection: Lazy Pre-Save Existence Guard

**Date:** 2026-08-18
**Status:** Accepted

## Context

Rana-linked files/folders can be renamed or deleted by another user or
another session while a QGIS project keeps a layer open referencing them.
Local-session renames/deletes are handled via existing Loader signals
(`20260818-1041-rename-delete-linking-local-session.md`), but that
mechanism only fires for changes made through this same session's Loader.

Research via `@rana-api` confirmed:

- The Rana backend offers **no push/webhook/websocket/SSE/polling-friendly
  change feed** — remote changes are fundamentally unobservable except by
  directly asking about the specific file.
- `descriptor_id` is a stable UUID, unaffected by rename/move (descriptor
  lookup is ID-based, no path involved).
- `file_path` (what this codebase calls `file_item["id"]`) is a path
  string that goes stale on rename/move (rename/move endpoints are
  path-based).
- Neither `GET file-descriptors/{descriptor_id}` nor
  `GET files/stat?path=...` documents an explicit "not found" status in
  the spec — any fetch failure must be treated as "no longer
  exists/accessible."
- No path is returned from the descriptor lookup, so there is no way to
  detect an ancestor-folder rename specifically from an ID-based lookup —
  but this turns out not to matter (see Decision).

### Options considered

**Option A — Lazy check-on-save only**: Immediately before executing a
save (style or data), call the cheapest relevant lookup
(`file-descriptors/{id}` for style, `files/stat?path=` for data). On
failure, clear refs, disable actions, warn, and abort the save without
queuing a task.

**Option B — Check on context-menu open too**: Additionally run the same
check whenever the layer-tree context menu is opened for a rana-linked
item/selection, so actions are pre-disabled rather than failing after
click.

**Option C — Background polling/watcher**: Periodically re-check all
rana-linked layers in the background.

## Decision

Option A — lazy check-on-save only.

## Reasoning

- No real-time detection mechanism exists on the backend, so any solution
  is inherently reactive; the question is only how eager to be
- Option B (menu-open) trades a smoother UX (pre-disabled menu) for an
  extra GET every time the menu opens, for a failure mode that's expected
  to be rare — judged not worth the added chattiness
- Option C (polling) adds ongoing background load and complexity to detect
  something that's cheap to check exactly when it matters (right before
  a save would actually execute)
- A single check per save action, using the ID-based lookup for style and
  path-based lookup for data, transparently covers three scenarios without
  separate logic for each: remote file delete, remote file rename (stale
  `file_path` fails the stat call), and remote ancestor-folder
  rename/delete (same stale-path failure) — because a stale full path
  fails identically regardless of whether the direct parent or an
  ancestor moved

## Consequences

### Positive
- Minimal added network traffic — one GET only at the moment a save is
  actually attempted
- Single code path handles delete, rename, and ancestor-rename scenarios
  uniformly

### Negative
- A user won't learn a file is gone until they attempt to save — the menu
  item will still appear enabled until clicked
- The close-project "sync all" flow must run this same guard per dirty
  layer and treat failures as "skip and report," not "abort the whole
  batch"

## Related Decisions

- `20260818-1041-rename-delete-linking-local-session.md`
- `20260818-1041-close-project-sync-prompt.md`
- `.minispec/specs/feat_454_open_generic_files/design.md` (Phase 3b)

## Notes

Researched via the `rana-api` subagent against the Rana OpenAPI spec on
2026-08-18. No rate-limit or cost documentation was found for the
candidate lookup endpoints, both of which require only `project_read`
auth.
