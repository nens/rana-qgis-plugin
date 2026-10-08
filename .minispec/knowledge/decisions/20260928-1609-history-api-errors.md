---
type: decision
id: 20260928-1609-history-api-errors
date: 2026-09-28
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/api.py
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/legacy/widgets/revisions_view.py
tags: [file-history, errors, compatibility]
participants: [engineer, implementation-agent]
---

# Make File-History Fetches Raise Standard API Errors

## Context

`get_tenant_project_file_history()` used a low-level `NetworkManager` call and
returned `None` for API failures. That made an empty history indistinguishable
from a failed request and differed from the newer API helpers, which raise
`RanaFetchError` while allowing `NetworkUnavailableError` to propagate.

The helper is also called by legacy code, so changing its parameter shape
would create unnecessary compatibility risk.

## Options Considered

### Option 1: Keep the parameter dictionary and use the standard fetch helper

Accept the existing `params` dictionary, including `path` and `limit`, and
delegate to `simple_fetch()`.

- ✅ Preserves the legacy call signature.
- ✅ Gives the new dialog reliable error semantics.
- ✅ Keeps the aggregation loop encapsulated in one wrapper.

### Option 2: Keep returning `None`

Handle `None` specially in the new dialog.

- ✅ Does not change the helper implementation.
- ❌ Cannot distinguish an empty result from an API failure.
- ❌ Preserves an inconsistent API contract.

### Option 3: Replace it with a new differently-shaped helper

Create a new typed helper with separate path/cursor arguments.

- ✅ Explicit function signature.
- ❌ Duplicates the existing endpoint wrapper.
- ❌ Risks breaking or leaving legacy callers inconsistent.

## Decision

We chose **Option 1: Keep the parameter dictionary and use the standard fetch
helper**. The function aggregates every cursor page internally (see
`20260928-1812-fetch-all-generic-history`) and raises on failure partway
through the aggregation, same as any other page.

## Consequences

### Positive

- ✅ Dialogs can show meaningful network/API errors.
- ✅ Existing legacy call sites retain their argument shape.
- ✅ Cursor aggregation is encapsulated in the wrapper rather than the UI.

### Negative

- ⚠️ Legacy callers do not yet present the new inline dialog error behavior.
- ⚠️ The dictionary remains less self-documenting than separate arguments.
- ⚠️ A failure partway through aggregation discards any pages already fetched
  for that call, since there is no partial-result return.

## Code References

- Existing helper: `rana_qgis_plugin/utils/api.py:get_tenant_project_file_history()`
- Standard helper: `rana_qgis_plugin/utils/api.py:simple_fetch()`
- Legacy caller: `rana_qgis_plugin/legacy/widgets/revisions_view.py:247`
