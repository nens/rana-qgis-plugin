# Decision: Rename get_style_file to get_file_descriptor_style

**Date:** 2026-04-15 10:55  
**Status:** Accepted  
**Supersedes:** 20260415-1045-unify-style-file-download-api.md (naming aspect)

## Decision

Rename `get_style_file()` to `get_file_descriptor_style()` for consistency with the naming pattern used by `get_publication_style()`.

## Rationale

The original name `get_style_file()` is too generic and doesn't clearly indicate what resource context it operates on. By comparing with the existing `get_publication_style()` function, the pattern should be `get_[resource]_[what]`:

- `get_publication_style()` - clearly operates on a publication
- `get_file_descriptor_style()` - clearly operates on a file descriptor

This makes the API self-documenting and consistent.

## Implementation

1. Rename function in `api.py`: `get_style_file()` → `get_file_descriptor_style()`
2. Update import in `download.py`
3. Update call site in `download.py`'s `get_style_zip()` method
