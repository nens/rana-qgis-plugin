---
feature: server-side-filtering
status: complete
created: 2026-06-18
decisions:
  - 20260618-1632-filter-architecture
  - 20260618-1632-projects-pagination-sorting
  - 20260618-1632-filterbar-debounce
---

# Server-Side Filtering Design

## Overview

Move filtering from client-side to server-side for projects, processes, and publications, using newly available backend API filter parameters. Files browser retains client-side filtering since the API doesn't offer filter support for that endpoint.

## Context

PR #384 introduced a shared `FilterBar` widget with client-side filtering across all four browsers. The backend now supports server-side filtering:

| Browser | Endpoint | `name` param | `who` param | `status` param |
|---------|----------|-------------|-------------|----------------|
| Projects | `GET /projects` | `search` (case-insensitive) | `project_user_id` | -- |
| Publications | `GET /publications` | `search` | `created_by` | -- |
| Processes | `GET /jobs` | `search` | `created_by` | `status` |
| Files | `GET /files/ls` | -- | -- | -- |

## Components

### FilterBar (modified)

**File:** `rana_qgis_plugin/widgets/filter_bar.py`

Changes:
- Replace `QLineEdit` with `DebouncedSearchBox` (400ms delay) for `TextFilterConfig` filters
- Combo filters (`ComboFilterConfig`) continue to emit immediately on selection
- Both still emit the same `filters_changed(dict)` signal
- No change to the public interface (`get_filters()`, `set_combo_items()`, `reset()`, etc.)

### ProjectsBrowser (major refactor)

**File:** `rana_qgis_plugin/widgets/projects_browser.py`

Current approach: fetches all projects (up to 1000) into a local list, filters/sorts/paginates client-side.

New approach:
- **Server-side filtering:** Pass `search` and `project_user_id` params to the API
- **Server-side pagination:** Use `limit: 100` + `offset` param. Each page is fetched on demand.
- **Server-side sorting:** Pass `ordering` param to the API. Column header clicks trigger a re-fetch.
- **Remove local caches:** `self.tenant_projects` and `self.filtered_projects` are no longer needed
- **Pagination reset:** Any filter or sort change resets `current_page` to 1
- **Who combo:** Populated from the current page's results (only shows relevant users)
- `_apply_filters()` becomes an API call instead of a list comprehension

### ProcessesBrowser (moderate changes)

**File:** `rana_qgis_plugin/widgets/processes_browser.py`

- `FilterBar.filters_changed` -> browser emits a signal with filter dict
- Signal flows up: `ProcessesBrowser` -> `RanaBrowser` -> `Loader.update_job_monitor_filters(filters)`
- Loader calls `worker.set_filters(filters)` then `scheduler.run_task_by_type(ProjectJobMonitorWorker)`
- Client-side sorting retained (no pagination UI)

Flicker-free update:
- A `_pending_full_refresh` flag is set when filters change
- When `add_items` is called with this flag set, it clears the model first then adds all items in the same slot call
- Flag is cleared after rebuild

### PublicationsBrowser (moderate changes)

**File:** `rana_qgis_plugin/widgets/publications_browser.py`

Same pattern as ProcessesBrowser:
- Signal flows up to `Loader.update_publication_monitor_filters(filters)`
- Loader calls `worker.set_filters(filters)` then `scheduler.run_task_by_type(PublicationMonitorWorker)`
- Client-side sorting retained

### FilesBrowser (no changes)

Retains current client-side filtering. API doesn't support filter params for the files endpoint.

### Persistent Workers (modified)

**File:** `rana_qgis_plugin/workers/persistent.py`

Both `ProjectJobMonitorWorker` and `PublicationMonitorWorker` get:
- A `set_filters(filters: dict)` method that:
  1. Stores filter params locally
  2. Clears tracked-item cache (`active_jobs` / `monitored_publications`)
- The `run()` method passes stored filter params to the API call

### Loader (new methods)

**File:** `rana_qgis_plugin/loader.py`

New methods:
- `update_job_monitor_filters(filters: dict)` -- calls worker's `set_filters()`, then `scheduler.run_task_by_type(ProjectJobMonitorWorker)`
- `update_publication_monitor_filters(filters: dict)` -- calls worker's `set_filters()`, then `scheduler.run_task_by_type(PublicationMonitorWorker)`

### API functions (modified)

**File:** `rana_qgis_plugin/utils/api.py`

- `get_tenant_projects()` -- accepts optional `params` dict for `search`, `project_user_id`, `ordering`, `limit`, `offset`
- `get_project_jobs()` -- accepts optional `params` dict for `search`, `created_by`, `status`
- `get_project_publications()` -- accepts optional `params` dict for `search`, `created_by`

## Signal Flow

### Projects (direct fetch)

```
FilterBar.filters_changed -> ProjectsBrowser._apply_filters() -> get_tenant_projects(params)
```

### Processes

```
FilterBar.filters_changed -> ProcessesBrowser emits filters_updated(dict)
  -> RanaBrowser relays -> Loader.update_job_monitor_filters(filters)
  -> worker.set_filters(filters) + scheduler.run_task_by_type(ProjectJobMonitorWorker)
  -> worker.run() fetches with params -> emits jobs_added(list)
  -> ProcessesBrowser.add_items() (clears model if _pending_full_refresh, then rebuilds)
```

### Publications

```
FilterBar.filters_changed -> PublicationsBrowser emits filters_updated(dict)
  -> RanaBrowser relays -> Loader.update_publication_monitor_filters(filters)
  -> worker.set_filters(filters) + scheduler.run_task_by_type(PublicationMonitorWorker)
  -> worker.run() fetches with params -> emits publications_added(list)
  -> PublicationsBrowser.add_items() (clears model if _pending_full_refresh, then rebuilds)
```

## API Parameter Mapping

| FilterBar key | Projects param | Processes param | Publications param |
|---------------|---------------|-----------------|-------------------|
| `name` (text) | `search` | `search` | `search` |
| `who` (combo) | `project_user_id` | `created_by` | `created_by` |
| `status` (combo) | -- | `status` | -- |

## Behavioral Notes

- **Filter persistence:** Filters persist when switching between sibling tabs (unchanged from current behavior)
- **Filter reset on navigation:** Filters reset when entering a project from ProjectsBrowser (unchanged)
- **Who combo population:** Always from locally available data -- current page results for projects, full worker results for processes/publications
- **Combo selection preservation:** Active combo selections survive when new items arrive (existing FilterBar behavior, unchanged)
- **Empty state:** If server returns no results for active filters, show the existing empty state

## Open Questions

- Exact API response format for `total` field when filters are applied (needed for pagination display)
- Whether the `ordering` param uses `+`/`-` prefix or `asc`/`desc` suffix (check API docs)
- If flicker is noticeable on processes/publications, may need to switch to diff-based model update

## Out of Scope

- Server-side sorting for processes and publications (small datasets, client-side is fine)
- Server-side filtering for files (API doesn't support it)
- Multi-select combo filters (current design is single-select)
