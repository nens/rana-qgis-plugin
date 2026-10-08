# Decision: Only vector files are expandable; layers fetched lazily from descriptor

**Date:** 2026-08-05
**Status:** Accepted

## Context

The Rana file descriptor (`GET /tenants/{tenant_id}/file-descriptors/{file_descriptor_id}`) contains a `layers` array. Each layer has `id`, `name`, and `type` (a geometry string or `null`). To know whether a file has layers at tree-build time, we would need to fetch descriptors for all files upfront.

## Decision

Only files with `data_type == "vector"` are treated as expandable. For these, `createChildren()` fetches the descriptor lazily (on expand) and returns `RanaLayerDataItem` children. All other data types are leaves.

## Reasoning

- Avoids fetching descriptors for all files upfront
- Vector is the only type where layers are meaningfully browsable in QGIS
- Simple rule: `data_type == "vector"` → expandable; everything else → leaf

## Layer icon mapping

QGIS theme icons are used, mapped from `layer.type`:

| `layer.type` | QGIS icon |
|---|---|
| `Point` | `mIconPointLayer.svg` |
| `LineString` | `mIconLineLayer.svg` |
| `Polygon` | `mIconPolygonLayer.svg` |
| `MultiPoint` | `mIconPointLayer.svg` |
| `MultiLineString` | `mIconLineLayer.svg` |
| `MultiPolygon` | `mIconPolygonLayer.svg` |
| `GeometryCollection` | `mIconGeometryCollectionLayer.svg` |
| `raster` | `mIconRaster.svg` |
| `null` / unknown | generic file icon |

## Consequences

- Files of other types with layers (if any) will not show them — acceptable for now
- If another data type gains layer support in future, the condition in `RanaFileDataItem` needs extending
