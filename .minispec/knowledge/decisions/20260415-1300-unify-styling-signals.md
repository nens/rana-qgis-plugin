# Decision: Unify File Descriptor Styling Signals and Methods

**Date:** 2026-04-15 13:00  
**Status:** Decided  
**Affected Components:** Loader, RanaBrowser, rana_qgis_plugin.py

## Context

After unifying the styling upload endpoints (vector and raster now use the same `FileDescriptorStyleUploadWorker`), the Loader still maintains separate signal pairs and methods:

- `save_vector_style()` and `save_raster_style()` methods
- `vector_style_finished` / `vector_style_failed` signals
- `raster_style_finished` / `raster_style_failed` signals

This creates unnecessary duplication in Loader and adds complexity in rana_qgis_plugin.py, which connects both signal pairs to the same UI handlers (`enable()` and `refresh()`).

## Decision

Unify the styling signal infrastructure in Loader:

1. **Replace separate signal pairs with:**
   - `file_descriptor_style_finished = pyqtSignal()`
   - `file_descriptor_style_failed = pyqtSignal(str)`

2. **Replace separate methods with:**
   - `save_file_descriptor_style(self, project, file)` — single method for both vector and raster
   - Extract `data_type` from `file['data_type']` to determine file type
   - Create appropriate `FileDescriptorStyleUploadWorker` internally

3. **Remove old handlers:**
   - Delete `on_vector_style_finished()`, `on_vector_style_failed()`
   - Delete `on_raster_style_finished()`, `on_raster_style_failed()`
   - Add unified `on_file_descriptor_style_finished(msg)` and `on_file_descriptor_style_failed(msg)`

4. **Keep schematisation separate:**
   - Existing `save_schematisation_style()` method unchanged
   - Reason: Different lifecycle (retry logic, 60-second timeout)
   - Schematisation signals remain independent

## Rationale

- **Eliminates duplication:** Single method and signal pair handle both vector and raster
- **Reduces complexity:** rana_qgis_plugin.py connects one signal instead of two
- **Maintains separation of concerns:** Schematisation kept separate due to different behavior
- **No UI changes:** RanaBrowser behavior identical (same final `enable()` and `refresh()` calls)
- **File dict already has data_type:** No need to pass as separate parameter

## Trade-offs

- **Not considered:** Merging schematisation into unified signals. Rejected because retry/timeout behavior is fundamentally different and would complicate the unified path.

## Implementation Notes

- Update Loader signal definitions (lines 136-140)
- Consolidate `save_vector_style` and `save_raster_style` logic into new `save_file_descriptor_style`
- Update worker instantiation to use `file['data_type']` and `DataType` enum
- Update rana_qgis_plugin.py signal connections (lines 443-447)
- No changes to worker classes, RanaBrowser, or schematisation handling
