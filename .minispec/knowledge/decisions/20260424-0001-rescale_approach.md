# Decision: Proportional Rescaling Approach for Color Ramp

**Date:** 2026-04-24  
**Status:** Accepted  
**Context:** When a raster's actual data range differs from the QML's fixed 0–1 range, how should colors be mapped?

## Problem

Given:
- Original QML color ramp: 9 color stops at values 0, 0.125, 0.25, ..., 1.0
- Actual raster range: e.g., elevation 0–1000 m, or water depth 0–5 m

Options:
1. **Proportional rescaling** — Compute each color stop's relative position in [0, 1], then map to [new_min, new_max]
2. **Preserve absolute values** — Leave color stops at their original values; only update classification bounds
3. **Manual remapping** — User manually edits the QML or the style in QGIS

## Decision: Proportional Rescaling

### Reasoning

Proportional rescaling preserves the **visual intent** of the style:

**Example: Elevation raster, range 0–1000**

Original QML stops:
```
0.0   → color A (dark)
0.5   → color E (light yellow)
1.0   → color I (light brown)
```

After rescaling to 0–1000:
```
0     → color A (dark)
500   → color E (light yellow)
1000  → color I (light brown)
```

The midpoint of the data range (500m) is still the lightest color, middle elevation shows the most striking color. The visual progression is preserved.

### Algorithm

For each color stop:
1. Normalize its value to [0, 1]: `t = (old_value - old_min) / (old_max - old_min)`
2. Map to new range: `new_value = new_min + t * (new_max - new_min)`
3. Keep color and label unchanged

### Implementation Detail: Transparency is NOT Rescaled

The QML's `<rasterTransparency>` rules (e.g., "make pixels with value 0–0.01 transparent") operate independently and are left unchanged. This is correct because:
- Transparency often targets absolute thresholds (e.g., "0 means nodata/dry")
- Relative transparency thresholds would be rare and unexpected
- Transparency rules are separate from the color ramp in the QML structure

## Alternatives Considered & Rejected

**Option 2 (Preserve absolute values):** Leave color stops at 0, 0.125, 0.25, ... even though the raster's range is 0–1000. Result: only 0–0.3 would use the color ramp; 0.3–1000 would be clamped to the last color. This is visually wrong and defeats the purpose of rescaling.

**Option 3 (Manual remapping):** Rejects automation entirely. Not feasible; users expect the plugin to "just work."

## Approval

Discussed with Margriet. Approved as part of overall design conversation.
