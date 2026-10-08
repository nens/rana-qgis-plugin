# Decision: Silent Abort on Missing Descriptor Data

**Date:** 2026-04-24  
**Status:** Accepted  
**Context:** What should happen when the file descriptor is missing, incomplete, or inaccessible at load time?

## Problem

When loading a raster with the `rana:physical_quantity_style` marker, we need descriptor data (specifically `descriptor["meta"]["range"]`). Scenarios where this data might be unavailable:
1. Descriptor fetch returns `None` (network error, permission issue, etc.)
2. `meta` key is missing or `None` (processing hasn't finished on the backend)
3. `range` key is missing or incomplete (incomplete metadata)

How should we respond?

## Decision: Silent Abort with Debug Logging

If any required field is missing or `None`:
1. **Abort rescaling** — skip the entire rescaling operation
2. **Continue loading** — layer loads with the original (unrescaled) style
3. **Log at debug level** — use `QgsMessageLog` with `Qgis.Info` level to record what happened (debug tools, not user-visible)
4. **No user warning** — do not show a warning dialog

### Reasoning

| Aspect | Reasoning |
|--------|-----------|
| **Fail-safe** | Unrescaled is better than error state. The layer still displays, and the user can manually adjust styling if needed. |
| **Not user-facing** | Missing descriptor data is a backend state issue, not a user action problem. Users don't need a warning. |
| **Operational visibility** | Debug logs are available for troubleshooting if needed. |
| **Precedent** | Existing code (e.g., vector layer style loading in `_add_all_layers_from_vector_file`) also silently falls back when metadata is incomplete. |

### Implementation Pattern

```python
descriptor = get_tenant_file_descriptor(file["descriptor_id"])
if descriptor is None:
    # Log and abort
    QgsMessageLog.logMessage(
        f"Descriptor fetch failed for {file_name}; skipping rescaling",
        "DEBUG", Qgis.Info
    )
    return

meta = descriptor.get("meta")
if not meta or not meta.get("range"):
    # Log and abort
    QgsMessageLog.logMessage(
        f"No range metadata for {file_name}; skipping rescaling",
        "DEBUG", Qgis.Info
    )
    return

value_range = meta["range"]
if not ("min" in value_range and "max" in value_range):
    # Log and abort
    QgsMessageLog.logMessage(
        f"Incomplete range data for {file_name}; skipping rescaling",
        "DEBUG", Qgis.Info
    )
    return

self._rescale_raster_renderer(layer, value_range["min"], value_range["max"])
```

## Alternatives Considered & Rejected

**Option A: Show user warning** — "Could not rescale layer due to missing metadata." Rejected because:
- Users can't act on this (it's a backend state, not a user error)
- Too noisy if it happens regularly during processing delays

**Option B: Raise an exception, fail layer load** — Rejected because:
- Prevents the layer from loading at all
- Worse UX than unrescaled but visible layer

## Approval

Discussed with Margriet. Confirmed that missing fields should be treated as mandatory for rescaling, so absence means silent abort.
