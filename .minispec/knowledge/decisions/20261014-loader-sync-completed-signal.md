---
type: decision
id: 20261014-loader-sync-completed-signal
date: 2026-10-14
status: superseded
supersedes: null
superseded_by: 20261014-native-dirty-property-notification
impacts:
  - rana_qgis_plugin/loader.py
tags: [sync, dirty-tracking, signals]
participants: [engineer, build agent]
---

# New `Loader.rana_sync_completed` Signal for Indicator Clearing

## Context

The layer-tree dirty indicator (see
`20261014-dirty-state-layer-tree-indicator.md`) needs to remove a badge once a
layer's dirty flag is actually cleared after a successful sync. Dirty flags
are *set* via native Qt signals already connected by
`dirty_tracking.attach_dirty_tracking` (`afterCommitChanges`, `styleChanged`),
but *clearing* happens inside `Loader`'s internal upload-completion handling
(`clear_dirty(...)` calls), with no existing signal an outside observer can
react to.

## Options Considered

### Option 1: New `Loader` signal, emitted at existing completion sites

Add `rana_sync_completed = pyqtSignal(list)`, emitted from the same code
paths that already call `clear_dirty` on success.
- ✅ Immediate, precise updates — no polling delay
- ✅ Purely additive; no change to existing upload/locking behavior
- ❌ One more public signal on an already large `Loader` class

### Option 2: Piggyback on the existing `WindowActivate` event filter

Re-scan all rana-linked layers' dirty flags whenever the main window regains
focus (a hook the plugin already installs for an unrelated refresh purpose).
- ✅ No `Loader` changes at all
- ❌ Indicator can stay visibly stale until the next focus-change event, even
  immediately after a sync the user just triggered from the same window
- ❌ Repurposes an unrelated hook for a different concern

### Option 3: Polling timer

Periodically re-check all rana-linked layers' dirty flags.
- ❌ Ongoing background cost for a precisely-known event (sync completion)

## Decision

This decision was superseded before feature implementation. A native
`QgsMapLayer.customPropertyChanged(key)` signal already reports dirty-property
addition and removal, so a new Loader signal would duplicate that notification
path. See `20261014-native-dirty-property-notification`.

## Consequences

### Positive
- The originally proposed signal would have enabled immediate clearing after
  successful sync.

- Superseded: adding the signal would unnecessarily grow `Loader`'s public
  signal surface when the layer itself already emits the required event.

## Related Decisions

- `20261014-dirty-state-layer-tree-indicator.md`
- `.minispec/specs/feat_470_file_sync/design.md`
