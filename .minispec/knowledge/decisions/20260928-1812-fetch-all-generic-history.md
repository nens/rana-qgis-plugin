---
type: decision
id: 20260928-1812-fetch-all-generic-history
date: 2026-09-28
status: superseded
supersedes: 20260928-1609-history-pagination
superseded_by: 20260930-async-history-fetch
impacts:
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/utils/api.py
tags: [file-history, pagination, api, consistency]
participants: [engineer, implementation-agent]
---

# Fetch All Generic History Eagerly, Matching Revision History

## Context

The original design paginated generic Rana history with a manual `Load more`
control backed by the endpoint's cursor. The schematisation revision decision
(`20260928-1808-revision-button-enablement`) was later changed to fetch all
revisions eagerly, because the revision action buttons need the complete
model count.

Having one history dialog page incrementally while the other fetches
everything up front is an inconsistent user experience for what is presented
as a single "Version history" feature. The codebase also already has a
precedent for eager cursor aggregation in `get_tenant_project_files()`, which
loops on `next` until exhausted before returning.

## Options Considered

### Option 1: Fetch all generic history pages eagerly

Aggregate every cursor page inside `get_tenant_project_file_history()` (or the
dialog), matching `get_tenant_project_files()`'s existing loop pattern, and
remove the `Load more` control from `HistoryDialog`.

- ✅ Consistent behavior across both history dialogs.
- ✅ Reuses an existing, already-accepted aggregation pattern in this codebase.
- ✅ Simpler dialog: no cursor/offset state to track across the session.
- ❌ A project/root with a very long history makes the initial synchronous
  fetch slower.

### Option 2: Keep `Load more` pagination for generic history only

Leave the original cursor-based `Load more` design in place while revisions
fetch eagerly.

- ✅ Bounds the initial generic-history request.
- ❌ Two different pagination UX patterns for one feature is confusing.
- ❌ Contradicts the stated goal of consistency between the two dialogs.

### Option 3: Single bounded page only, no way to see older entries

- ✅ Smallest possible implementation.
- ❌ Users cannot see older history from the plugin at all.
- ❌ Rejected earlier in the original pagination decision for the same reason.

## Decision

We chose **Option 1: Fetch all generic history pages eagerly**.
`get_tenant_project_file_history()` will loop over the endpoint's `next`
cursor internally, aggregating all `items` before returning, mirroring
`get_tenant_project_files()`. `HistoryDialog` fetches the complete history on
open and on Refresh; it no longer has a `Load more` control or cursor state.

This makes both `HistoryDialog` and `SchematisationRevisionHistoryDialog`
consistent: both fetch their complete data set synchronously before
rendering.

## Consequences

### Positive

- ✅ One consistent loading behavior across both history dialogs.
- ✅ Removes cursor-state bookkeeping from the dialog.
- ✅ Reuses an established aggregation pattern rather than inventing a new one.

### Negative

- ⚠️ A project or root folder with very long history can make the initial
  fetch noticeably slower, with no bounded fallback.
- ⚠️ A failure partway through aggregation surfaces as a single error with no
  partial results, same trade-off already accepted for revisions.

## Code References

- Existing eager cursor-aggregation pattern:
  `rana_qgis_plugin/utils/api.py:207` (`get_tenant_project_files`)
- Superseded generic-history pagination design:
  `20260928-1609-history-pagination`
- Matching revision decision: `20260928-1808-revision-button-enablement`

## Related Decisions

- `20260928-1609-history-pagination` (superseded)
- `20260928-1609-history-api-errors`
- `20260928-1808-revision-button-enablement`
