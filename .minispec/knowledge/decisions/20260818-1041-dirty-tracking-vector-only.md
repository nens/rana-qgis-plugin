# Dirty-State Tracking: Vector Data Only, All Layer Types for Style

**Date:** 2026-08-18
**Status:** Accepted

## Context

Layer-panel items should visibly indicate when local style or data has
changed since the last sync to Rana. QGIS provides signals for vector
layer edits (`afterCommitChanges`/`editingStopped`) and for style changes
(`styleChanged`, on any layer type), but has no signal for raster data
changes — raster editing in place isn't generally supported, and there's
no cheap way to detect a raster's source file changing externally.

## Decision

- Track `rana/data_dirty` for vector layers only, via
  `afterCommitChanges`/`editingStopped`.
- Track `rana/style_dirty` for all layer types, via `styleChanged`.
- Raster "save data" stays always-enabled with no dirty gating.

## Reasoning

- There is no reliable signal to compute raster data dirtiness — building
  one (e.g. mtime polling) adds complexity for a rarely-needed capability,
  since in-QGIS raster editing isn't a common workflow
- `styleChanged` fires for many kinds of changes (including cosmetic ones
  like scale-based visibility), but the dirty flag is idempotent — no
  debouncing needed, it just stays set until the next successful style
  sync

## Consequences

- Users may occasionally see a raster's "save data" active with no way to
  tell if it's actually needed — acceptable, matches Option "vector-only
  dirty tracking" as agreed
- Any `styleChanged` emission marks style dirty, even for changes some
  users might consider inconsequential — simpler than trying to
  distinguish "meaningful" from "cosmetic" style changes

## Related Decisions

- `.minispec/specs/feat_454_open_generic_files/design.md` (Phase 2)
