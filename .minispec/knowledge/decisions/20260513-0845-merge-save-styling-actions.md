# Merge Save Styling Actions

**Date**: 2026-05-13
**Status**: Accepted
**Context**: SAVE_VECTOR_STYLING and SAVE_RASTER_STYLING have identical labels, tooltips, and icons in the new spec

## Decision

Merge `SAVE_VECTOR_STYLING` and `SAVE_RASTER_STYLING` into a single `SAVE_STYLING` action with one signal (`save_styling_requested`).

## Rationale

Both signal chains connect to the same handler (`loader.save_file_descriptor_style`), which determines vector vs raster internally from the file's `data_type` field. The two separate actions and signals exist only to provide different labels, but the new spec uses "Save style" for both. There is no functional reason to keep them separate.
