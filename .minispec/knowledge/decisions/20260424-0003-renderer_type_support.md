# Decision: Support QgsSingleBandPseudoColorRenderer Only (Initially)

**Date:** 2026-04-24  
**Status:** Accepted  
**Context:** Which raster renderer types should support rescaling?

## Problem

QGIS supports multiple raster renderer types:
- `QgsSingleBandPseudoColorRenderer` — single band with color ramp (elevation, water depth, etc.)
- `QgsSingleBandGrayRenderer` — single band rendered as grayscale
- `QgsMultiBandColorRenderer` — multi-band, no single continuous range
- `QgsRasterLayer` with other custom renderers

Not all have rescalable color ramps. Should we support all types or only some?

## Decision: Support QgsSingleBandPseudoColorRenderer Only

### Reasoning

| Renderer Type | Support? | Why |
|---|---|---|
| **QgsSingleBandPseudoColorRenderer** | ✅ Yes | Has a color ramp with discrete stops (like both example QMLs). Rescaling is straightforward and meaningful. |
| **QgsSingleBandGrayRenderer** | ❌ No (skip) | Renders as grayscale; no color ramp. Classification bounds may matter, but no color stops to rescale. Could add support later if needed. |
| **QgsMultiBandColorRenderer** | ❌ No (skip) | Multi-band RGB; no single continuous range to rescale. Out of scope. |
| **Other types** | ❌ No (skip) | Future extensibility; support on demand. |

### Implementation

```python
from qgis.core import QgsSingleBandPseudoColorRenderer

renderer = layer.renderer()
if not isinstance(renderer, QgsSingleBandPseudoColorRenderer):
    # Skip rescaling; layer uses original style
    return
```

If an unsupported type is encountered, the layer loads with the original style unchanged (no warning, no error).

### Future Extension

If evidence shows that other renderer types need rescaling:
1. `QgsSingleBandGrayRenderer` — could rescale classification min/max
2. Others — add support with separate decision record

## Alternatives Considered & Rejected

**Option A: Support all renderer types** — Rejected because:
- Over-engineering for current use case (physical_quantity styles are always pseudocolor)
- Risk of unintended behavior for types we haven't tested
- Can add types incrementally as needed

**Option B: Error on unsupported types** — Rejected because:
- Prevents layer from loading
- Worse UX than graceful degradation

## Approval

Discussed with Margriet. Confirmed that pseudocolor-only is sufficient for this feature; other types can be added in follow-up work.
