---
id: 20260921-1800-wms-module-level-layer-opening
status: accepted
date: 2026-09-21
---

# Use module-level WMS layer opening

## Context

The legacy implementation opens scenario WMS layers through the old
`FileLayerManager` class hierarchy. The active plugin has moved file and layer
opening toward module-level functions such as `open_rana_raster` and
`open_rana_vector_layer`. The old layer-manager classes are not imported by
the active loader and are only referenced by unreachable legacy code.

## Decision

Implement a new module-level `open_rana_wms` function. Reuse the legacy WMS
URI construction, but use current Rana group helpers to add layers. WMS
layers remain plain `QgsRasterLayer` instances and do not receive
`RanaLayerRef` metadata or dirty tracking.

After a complete reference check, remove the obsolete
`LayerManager`/`FileLayerManager`/`PublicationLayerManager` hierarchy rather
than retaining a second WMS implementation.

## Rationale

This follows the active architecture and avoids preserving dead class-based
code. WMS layers are remote views rather than local editable files, so Rana
file references and dirty tracking do not provide value for this feature.
