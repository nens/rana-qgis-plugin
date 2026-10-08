# Layer-Tree Group Structure: Reuse by Name

**Date:** 2026-08-18
**Status:** Accepted

## Context

Opening a Rana file/layer needs to place it in a `QgsLayerTreeGroup`
hierarchy mirroring the Rana tree path (`project/files/foo/bar.gpkg`).
Repeated opens of files under the same folder need a rule for whether to
reuse existing groups or always create new ones.

### Options considered

**Option A — Find-or-create by name**: Walk the path segments, looking up
an existing `QgsLayerTreeGroup` by name at each level before creating a new
one. Adapted from legacy `LayerManager.add_layer`.

**Option B — Always create new groups**: Each open action creates a fresh
group tree, even if a matching one already exists.

## Decision

Option A — find-or-create by name.

## Reasoning

- Matches the behavior a user would expect: opening the same file twice
  should not produce `bar.gpkg (2)`-style duplicate groups
- Directly reuses the pattern already proven in the legacy `LayerManager`
  (`add_layer`), adapted to be driven by the Rana path rather than a
  downloaded local file path
- Avoids layer-tree clutter that would otherwise accumulate over a working
  session

## Consequences

- Group matching is by display name only, not by any hidden rana reference
  — if a user manually renames a group, a later open may create a sibling
  group instead of reusing it. This is an acceptable, documented trade-off.

## Related Decisions

- `.minispec/specs/feat_454_open_generic_files/design.md` (Phase 1)
