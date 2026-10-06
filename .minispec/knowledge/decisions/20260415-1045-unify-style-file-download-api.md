# Decision: Unify Style File Download API

**Date:** 2026-04-15 10:45  
**Status:** Accepted  
**Context:** The styling endpoints have been refactored to use a single unified endpoint (`/styles/{file_name}`) instead of type-specific endpoints (`/{raster|vector}-style/{file_name}`)

## Decision

Remove the `source_type` parameter from `get_style_file()` and eliminate the wrapper functions `get_raster_style_file()` and `get_vector_style_file()`.

## Options Considered

### Option A: Keep `get_style_file` as primary function (CHOSEN)
- Remove `source_type` parameter from `get_style_file(descriptor_id, file_name)`
- Delete wrapper functions `get_raster_style_file()` and `get_vector_style_file()`
- Update callers in `download.py` to call `get_style_file()` directly
- **Pros:**
  - Cleaner function signature
  - Aligns with existing `get_*` naming convention in api.py
  - Removes unnecessary wrapper functions
- **Cons:** None significant

### Option B: Rename to `download_style_file`
- More explicit about the action (downloads content, not just gets metadata)
- Follows patterns like `start_file_upload`, `finish_file_upload`
- **Cons:** Breaks with dominant `get_*` prefix pattern in api.py

### Option C: Rename to `fetch_file_descriptor_style`
- Very explicit and clear
- **Cons:** Longer name, doesn't match existing conventions

## Implementation

1. Update `get_style_file()` signature: remove `source_type` parameter
2. Update endpoint URL: change from `/{source_type}-style/{file_name}` to `/styles/{file_name}`
3. Delete `get_raster_style_file()` and `get_vector_style_file()`
4. Update imports in `download.py` to remove the wrapper functions
5. Update `get_style_zip()` in `download.py` to call `get_style_file()` directly

## Rationale

The unified endpoint eliminates the need for type-specific logic at the API level. The caller (`download.py`) doesn't need to care about the type distinction anymore—it just requests the style file by descriptor and filename. This is simpler and more maintainable.
