---
type: decision
id: 20260803-0813-project-fetch-error-handling
date: 2026-08-03
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/api.py
  - rana_qgis_plugin/data_items/rana_item.py
tags: [api, error-handling, fetch]
participants: [engineer, implementation-agent]
---

# get_tenant_projects raises FetchError; createChildren handles it

## Context

`get_tenant_projects` currently accepts a `communication` object and swallows exceptions
with `communication.show_error(...)`. In the datasource architecture, `createChildren()`
has no natural way to pass a `communication` handle into utility functions. The error
reporting layer should be at the call site, not buried in the fetch function.

## Decision

`get_tenant_projects` is refactored to:
- Drop the `communication` parameter
- Raise `FetchError` on failure (already defined in `utils/api.py`)

`RanaRootDataItem.createChildren()` catches `FetchError` and reports via
`self.communication.show_error(...)`.

This follows the pattern already established by `FetchError` in the codebase and keeps
fetch functions free of UI concerns.

## Consequences

### Positive
- ✅ Fetch functions are pure — no UI dependencies
- ✅ Consistent with existing `FetchError` usage
- ✅ Call sites decide how to present errors

### Negative
- ⚠️ Any other callers of `get_tenant_projects` must be updated to handle `FetchError`

## Code References

- `rana_qgis_plugin/utils/api.py` — `get_tenant_projects`, `FetchError`
- `rana_qgis_plugin/data_items/rana_item.py` — `RanaRootDataItem.createChildren`
