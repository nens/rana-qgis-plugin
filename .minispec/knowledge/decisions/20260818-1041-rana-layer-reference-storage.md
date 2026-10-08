# Rana Layer Reference Storage

**Date:** 2026-08-18
**Status:** Accepted

## Context

Layers opened from Rana into the QGIS layer panel need to carry enough
reference data (project id, file path, descriptor id, layer id) to later
support save-style/save-data actions, dirty tracking, and rename/delete
linking. This data needs to survive project save/reload.

### Options considered

**Option A — `QgsMapLayer.setCustomProperty()`**: Store rana refs as
key/value pairs directly on each layer (`rana/project_id`, `rana/file_path`,
`rana/descriptor_id`, `rana/layer_id`), accessed via a small typed helper
module.

**Option B — External registry**: A central dict or QGIS project variable
mapping layer id -> rana refs, maintained alongside QGIS's own layer
lifecycle.

## Decision

Option A — `QgsMapLayer.setCustomProperty()`.

## Reasoning

- Persists automatically with the `.qgz`/`.qgs` project file — no manual
  serialization step needed for refs to survive close/reopen
- No second source of truth to keep in sync with QGIS's own layer add/remove
  (layers can be removed directly by the user in the panel)
- Naturally scoped per-layer, matching the granularity needed for
  per-layer style save and per-layer dirty tracking

## Consequences

- A thin helper module (`utils/rana_layer_refs.py`) is needed to keep key
  names and typed access consistent: `set_rana_refs()`, `get_rana_refs()`,
  `is_rana_linked()`
- Bulk queries ("all rana-linked layers in the project") require iterating
  `QgsProject.instance().mapLayers()` and checking each layer's custom
  properties — acceptable given expected project sizes

## Related Decisions

- `.minispec/specs/feat_454_open_generic_files/design.md` (Phase 1)
