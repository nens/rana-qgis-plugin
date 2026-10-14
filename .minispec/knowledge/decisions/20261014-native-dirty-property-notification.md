---
type: decision
id: 20261014-native-dirty-property-notification
date: 2026-10-14
status: accepted
supersedes: 20261014-loader-sync-completed-signal
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/indicator_manager.py
tags: [dirty-tracking, layer-tree, signals]
participants: [engineer, build agent]
---

# Use `QgsMapLayer.customPropertyChanged` for Dirty Indicator Updates

## Context

The initial indicator design added `Loader.rana_sync_completed` so badges
could be updated both when a layer became dirty and after a successful sync.
However, QGIS emits `QgsMapLayer.customPropertyChanged(key)` when
`setCustomProperty()` and `removeCustomProperty()` modify a property. Existing
dirty tracking uses those methods to set and clear `rana/data_dirty` and
`rana/style_dirty`.

The first IndicatorManager draft also listened independently to
`afterCommitChanges` and `styleChanged`, duplicating subscriptions already
owned by `dirty_tracking.attach_dirty_tracking`.

## Options Considered

### Option 1: Native custom-property notification

Listen to each tracked layer's `customPropertyChanged(key)`, filtering for the
two dirty property names. Let existing dirty tracking remain the only writer
and the dirty custom properties remain the source of truth.
- ✅ One notification path for dirtying and clearing
- ✅ No second listener on edit/style signals
- ✅ No new Loader completion signal or separate dirty-state cache
- ❌ Indicator manager must connect to each eligible layer's property signal

### Option 2: Dedicated Loader completion signal plus edit/style listeners

Use QGIS edit/style signals to update badges when dirty, and a new Loader
signal to clear badges on successful sync.
- ✅ Explicit signal contract for successful sync
- ❌ Duplicates subscriptions to edit/style events
- ❌ Adds a Loader signal despite the layer already exposing property changes

## Decision

We chose **Option 1**. `IndicatorManager` listens only to
`customPropertyChanged(key)` for `rana/data_dirty` and `rana/style_dirty`.
The existing dirty-tracking callbacks remain the only listeners to
`afterCommitChanges` and `styleChanged`. When a successful sync removes a dirty
property, the layer emits the same notification and the badge is updated.

## Consequences

### Positive
- ✅ Existing custom properties remain the single source of truth
- ✅ No duplicate dirty-state event subscriptions or Loader signal
- ✅ Addition and removal of dirty flags share one update path

### Negative
- ⚠️ Indicator refresh depends on dirty properties continuing to be changed
  through QGIS's `setCustomProperty`/`removeCustomProperty` APIs

## Code References

- Dirty flags are set in `rana_qgis_plugin/layer_management/dirty_tracking.py`
- Dirty flags are cleared in `rana_qgis_plugin/loader.py` through
  `clear_dirty()`
- Indicator observer is `rana_qgis_plugin/layer_management/indicator_manager.py`

## Related Decisions

- `20261014-loader-sync-completed-signal` (superseded)
- `20261014-dirty-state-layer-tree-indicator`
- `.minispec/specs/feat_470_file_sync/design.md`

## Notes

QGIS 4.x API/source research confirmed that `setCustomProperty()` and
`removeCustomProperty()` emit `customPropertyChanged(key)`.
