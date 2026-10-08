---
id: 20260922-1130-result-grouping-by-file-path
date: 2026-09-22
status: accepted
---

# Group Results Analysis Layers by Rana File Path

## Context

Results Analysis currently groups simulations derived from the same schematisation/grid. Rana users instead need each result grouped below the file from which it was opened, for example `project/files/folder/result.zip`. Rana already represents file and schematisation locations as ordered `parents` path segments and uses that convention for layer placement.

## Options considered

1. **Pass a `QgsLayerTreeGroup` object**: strong identity, but couples the two plugins to a QGIS object lifecycle and API.
2. **Pass a `list[str]` path**: reuses the existing Rana convention and lets Results Analysis use its existing path-based group helper.
3. **Overload the existing project string**: smallest apparent API change, but conflates project and file location and does not clearly express the contract.

## Decision

Use option 2. Rana passes an optional `group_path: list[str]` to Results Analysis. The path is built as `[project_name, "files"] + file_item["id"].split("/")`. Results Analysis creates or reuses that path and attaches its result groups directly under the final file group. The grid-name subgroup is omitted in this branch because the file group identifies the result source.

## Reasoning

- Matches how Rana already opens schematisations, vectors, and rasters.
- Keeps the cross-plugin contract primitive and independent of QGIS object ownership.
- Reuses Results Analysis' existing `_get_or_create_group_alternative_structure(parents)` helper.
- Avoids grouping unrelated result files together merely because they share a schematisation.
- Preserves the established name-based find-or-create behavior documented in `20260818-1041-group-structure-reuse`.

## Consequences

- Results Analysis gains an additive optional parameter and a new precedence branch.
- File-grouped results have no redundant grid-name subgroup.
- Path names are display/path segments, not hidden stable identifiers; this is consistent with existing Rana grouping behavior.
- Standalone Results Analysis and older project-aware callers retain their current structures.

## Related decisions

- `20260818-1041-group-structure-reuse`
- `20260922-1131-cross-repository-compatibility`
