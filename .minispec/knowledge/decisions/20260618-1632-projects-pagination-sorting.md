---
id: 20260618-1632-projects-pagination-sorting
status: accepted
date: 2026-06-18
---

# Projects: Server-Side Pagination and Sorting

## Context

ProjectsBrowser currently fetches up to 1000 projects, caches them locally, and does client-side filtering, sorting, and pagination (100 per page). With server-side filtering, we need to decide whether pagination and sorting should also move server-side.

## Decision

Move all three to server-side for projects:
- **Filtering:** `search` and `project_user_id` params
- **Pagination:** `limit: 100` + `offset` param, each page fetched on demand
- **Sorting:** `ordering` param, triggered by column header clicks

Remove local caches (`self.tenant_projects`, `self.filtered_projects`). Any filter or sort change resets to page 1.

## Alternatives Considered

- **Server-side filtering only, keep client-side pagination/sorting (Option A):** Rejected -- with server-side pagination, sorting client-side only sorts within a page, which is meaningless. If we paginate server-side, we must sort server-side too.
- **Keep everything client-side with 1000 limit:** Rejected -- defeats the purpose of server-side filtering and doesn't scale.

## Consequences

- Each user action (filter change, sort change, page change) triggers an API call
- Debouncing (400ms) on text input mitigates excessive calls
- "Who" combo is populated from current page results only (shows relevant users in view)
- Simpler local state -- no large project list cached in memory
