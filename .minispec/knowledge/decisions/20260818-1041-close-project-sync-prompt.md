# Close-Project Sync Prompt via `aboutToBeCleared`

**Date:** 2026-08-18
**Status:** Accepted

## Context

When closing a project (or opening a new one, or quitting QGIS) with
unsynced rana-linked layers, the user should be warned and offered a
chance to sync all before proceeding. The plugin already installs an
event filter on the main window (`rana_qgis_plugin.py`), but only for
`WindowActivate`/`WindowDeactivate` (focus-regain refresh) — nothing
hooks project close today.

## Decision

Hook `QgsProject.instance().aboutToBeCleared`, which fires before project
close, new-project, and app quit. On fire, scan rana-linked layers for
dirty flags (`rana/data_dirty`, `rana/style_dirty`) and prompt "Sync all
now / Discard / Cancel."

## Reasoning

- It's the closest available signal to "project is about to go away" that
  fires before the layer set is cleared, so dirty layers can still be
  inspected
- No alternative was found that is both cancelable and fires early enough
  to inspect layer state — see limitation below

## Consequences

### Known limitation

- `aboutToBeCleared` is **not cancelable** — showing a modal prompt inside
  the slot works (it blocks synchronously), but "Cancel" in that prompt
  can only mean "skip syncing now," not "abort the close/quit." This is a
  deliberate, documented constraint, not something this design attempts to
  solve.
- The sync-all flow triggered from this prompt must run the remote-change
  guard (`20260818-1041-remote-change-lazy-guard.md`) per layer and
  exclude/report failures rather than abort the whole batch, since some
  dirty layers may have gone stale remotely.

## Related Decisions

- `20260818-1041-remote-change-lazy-guard.md`
- `.minispec/specs/feat_454_open_generic_files/design.md` (Phase 3)
