---
id: 20260922-1505-per-result-layer-ownership
date: 2026-09-22
status: accepted
---

# Give Each Grouped Result Independent QGIS Layers

## Context

Results Analysis currently reuses one `ThreeDiGridItem` and one set of QGIS
computational-grid layers when multiple results use the same grid. Result fields
are added to those shared layers. Passing `group_path` only through the grid
validation signal would therefore work for the first result but fail for later
results that reuse the already-loaded grid and bypass `grid_valid`.

The requested behavior is a complete tree per result, with the computational
grid and Results Analysis tool groups directly below the result's Rana file
group. Result fields, visibility, styling, and cleanup must not leak between
results.

## Options considered

1. **Reuse one QGIS layer set in multiple layer-tree groups**: avoids memory
   duplication, but the groups would still share fields, visibility, styling,
   and lifecycle. It does not provide true per-result ownership.
2. **Recompute the grid independently for every result**: gives ownership, but
   repeats the expensive H5-to-GeoPackage conversion and unnecessary source
   processing.
3. **Share the generated GeoPackage and create independent QGIS layers per
   result**: preserves a single expensive grid conversion while isolating
   mutable QGIS state.

## Decision

Use option 3. Results Analysis will:

- reuse the generated computational-grid GeoPackage for results using the same
  grid;
- maintain a clean source-layer representation for grouped results;
- create independent QGIS layer instances for each grouped result, using the
  QGIS clone/copy mechanism;
- store result-owned layer IDs and the result file group on
  `ThreeDiResultItem`;
- add result fields and result-specific tool groups only to/under that result;
- keep the current shared-grid implementation when `group_path` is absent.

The `group_path` must travel through the result-validation signal, not only the
new-grid signal, because a later result can reuse an existing grid.

## Consequences

- Grouped results use additional memory for independent QGIS layer instances;
  this is required for true isolation and is limited to layer copying, not
  repeated H5-to-GeoPackage conversion.
- Results Analysis consumers that currently read `grid_item.layer_ids` or
  `grid_item.layer_group` in a result-specific context must use result-owned
  references in grouped mode and retain the grid references as a legacy fallback.
- Result serialization must persist enough grouped metadata to avoid creating
  duplicate layers when a project is reopened.
- Automated tests can cover layer ownership and cleanup using the existing
  real-QGIS test fixture. Visual rendering, interaction, performance, and
  cross-plugin mixed-version behavior still require manual QGIS validation.

## Related decisions

- `20260922-1130-result-grouping-by-file-path`
- `20260922-1131-cross-repository-compatibility`
