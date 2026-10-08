---
type: decision
id: 20260803-0812-project-fetch-strategy
date: 2026-08-03
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/api.py
tags: [api, projects, fetch, performance]
participants: [engineer, implementation-agent]
---

# Full fetch for now; incremental by updated_at as future optimisation

## Context

Projects are expected to change rarely. Fetching everything on each refresh is wasteful
in the common case. An incremental strategy (fetch only items newer than last poll) was
considered. The API `project_list` endpoint supports `order_by` and exposes `updated_at`
on each project, which would enable sorting descending and stopping pagination when items
are older than the last fetch timestamp. `updated_at` would also cover renames and status
changes (including soft-deletion).

## Options Considered

### Option A: Full fetch always
- ✅ Simple, no state to manage
- ✅ Always consistent
- ❌ Fetches unchanged data on every refresh

### Option B: Incremental fetch by `updated_at`
- ✅ Only transfers new/changed items
- ✅ Covers creates, renames, soft-deletes via status change
- ❌ Requires storing last-fetch timestamp
- ❌ `order_by=updated_at` not yet confirmed to work (undocumented allowed values)
- ❌ Adds complexity before the basic flow is proven

## Decision

We chose **Option A** for this task.

For a list of a few hundred projects, a full fetch is fast enough. The incremental path
via `updated_at` is well-understood and documented here for future implementation once
`order_by=updated_at` is confirmed to work against the live API.

## Consequences

### Positive
- ✅ No timestamp state to persist or invalidate
- ✅ Always fully consistent list

### Negative
- ⚠️ Fetches all pages on every refresh, even when nothing changed

## Future Path

When ready to optimise:
1. Confirm `order_by=updated_at` works on `project_list` endpoint
2. Store last-fetch timestamp (e.g. in `QgsSettings`)
3. In refresh path: fetch pages sorted by `updated_at` desc, stop when item
   `updated_at` < last-fetch timestamp
4. Merge results into existing children using `addChildItem()` / `deleteChildItem()`

## Code References

- `rana_qgis_plugin/utils/api.py` — `get_tenant_projects`, `paginated_fetch`
