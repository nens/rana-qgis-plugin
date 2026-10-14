---
type: decision
id: 20261014-dirty-state-layer-tree-indicator
date: 2026-10-14
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/indicator_manager.py
tags: [dirty-tracking, layer-tree, ui]
participants: [engineer, build agent]
---

# Dirty-State Visual Indicator: `QgsLayerTreeViewIndicator`, Layer + Aggregated Group Badges

## Context

`feat_454_open_generic_files` added `rana/data_dirty`/`rana/style_dirty`
tracking but explicitly left "visual treatment of the dirty-state indicator"
out of scope. This decision picks it: what mechanism, what granularity, and
what interaction model.

## Options Considered

### Option 1: `QgsLayerTreeViewIndicator` (small icon badge next to the node)

QGIS's native mechanism for attaching badges to layer-tree nodes
(`QgsLayerTreeView.addIndicator(node, indicator)`). Confirmed via API
research: works on both `QgsLayerTreeLayer` and `QgsLayerTreeGroup`, supports
multiple indicators per node, has `clicked`/tooltip support. Indicators are
not auto-cleaned-up on node/view teardown — the caller must remove them
explicitly.
- ✅ Native QGIS mechanism, used for exactly this kind of badge use case
- ✅ Works on both layer and group nodes, enabling aggregation
- ❌ Requires explicit lifecycle management (no auto-cleanup)

### Option 2: Font/color formatting of the node label (e.g. italic, bold)

Would require overriding `QgsLayerTreeModel` data roles
(`Qt::FontRole`/`Qt::ForegroundRole`) — no precedent in this codebase, more
invasive, no built-in click/tooltip support.
- ❌ No existing pattern to build on; needs a custom model/delegate
- ❌ Harder to combine cleanly with group-level aggregation

## Decision

We chose **`QgsLayerTreeViewIndicator`**, attached both to the dirty layer
node directly and aggregated onto every ancestor group node up to the root —
so a collapsed folder/file group still surfaces that something inside is
unsynced. One generic icon/tooltip is used regardless of whether it's style,
data, or both dirty; clicking only shows the tooltip (does not trigger a
sync).

## Consequences

### Positive
- ✅ Native, QGIS-blessed mechanism; no custom model/delegate needed
- ✅ Visible even with groups collapsed — matches the feature's purpose
  (don't miss unsynced state)
- ✅ Reuses existing group-traversal helpers already used for building menu
  actions (`LayerTreeMenuProvider.file_groups`/`collect_all_layers`)

### Negative
- ⚠️ Indicators require explicit add/remove bookkeeping on layer/group
  add/remove — must not rely on QGIS to auto-purge stale indicator objects
- ⚠️ No visual distinction between style-dirty and data-dirty — a user must
  check the context menu to know which action is relevant

## Related Decisions

- `20260818-1041-dirty-tracking-vector-only.md`
- `.minispec/specs/feat_454_open_generic_files/design.md` (Phase 2, listed
  this as out of scope)
- `.minispec/specs/feat_470_file_sync/design.md`

## Notes

API confirmed via `@docs-research` against QGIS 4.x API docs/source
(`qgslayertreeviewindicator.h`, `qgslayertreeview.cpp`) on 2026-10-14.
