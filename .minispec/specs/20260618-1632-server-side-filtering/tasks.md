---
feature: server-side-filtering
status: complete
created: 2026-06-18
chunk_size: medium
total_tasks: 9
estimated_lines: 320
---

# Server-Side Filtering Tasks

## Overview
Move filtering from client-side to server-side for projects, processes, and publications. Ordered by widget so each browser can be manually tested end-to-end before moving to the next.

## Task List

### Foundation

#### Task 1: FilterBar: Replace QLineEdit with DebouncedSearchBox
- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/widgets/filter_bar.py`
- **Description:** Swap QLineEdit with DebouncedSearchBox (400ms delay) for TextFilterConfig filters. Wire `searchChanged` signal to emit `filters_changed(dict)`. Combo filters remain immediate.
- **Depends on:** None
- **Acceptance:** All four browsers still show filter bar. Typing in the name field debounces (no signal until 400ms after last keystroke). Combo selections fire immediately.

#### Task 2: API functions: Add filter/pagination params
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/utils/api.py`
- **Description:** Update `get_tenant_projects()` to accept optional params for `search`, `project_user_id`, `ordering`, `limit`, `offset`. Update `get_project_jobs()` to accept optional params for `search`, `created_by`, `status`. Update `get_project_publications()` to accept optional params for `search`, `created_by`. All new params are forwarded to the API call.
- **Depends on:** None
- **Acceptance:** Existing callers continue to work without changes (params are optional). No unit tests -- these functions wrap HTTP calls and testing param merging alone has no value.

### ProcessesBrowser

#### Task 3: Worker: Add set_filters to ProjectJobMonitorWorker
- **Estimate:** ~15 lines
- **Files:** `rana_qgis_plugin/workers/persistent.py`
- **Description:** Add `set_filters(filters: dict)` method to `ProjectJobMonitorWorker`. Method stores filters locally and clears `self.active_jobs` cache. Update `run()` to pass stored filters to `get_project_jobs()`.
- **Depends on:** Task 2
- **Acceptance:** Unit test: calling `set_filters({"search": "foo"})` stores params and empties `active_jobs`. `run()` passes filters to the API function.

#### Task 4: Loader + signal wiring for processes
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/widgets/processes_browser.py`, `rana_qgis_plugin/widgets/rana_browser.py`, `rana_qgis_plugin/rana_qgis_plugin.py`
- **Description:** Add `update_job_monitor_filters(filters: dict)` to Loader (calls worker's `set_filters()` then `scheduler.run_task_by_type(ProjectJobMonitorWorker)`). Add `filters_updated = pyqtSignal(dict)` to ProcessesBrowser, emit on `filters_changed`. Wire signal through RanaBrowser to Loader.
- **Depends on:** Task 3
- **Acceptance:** Manual: changing a filter in ProcessesBrowser triggers the worker to re-fetch with new params (verify via logging or debugger).

#### Task 5: ProcessesBrowser: Full-refresh on filter change
- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/widgets/processes_browser.py`
- **Description:** Add `_pending_full_refresh` flag, set to True when `filters_changed` fires. In `add_items`, if flag is set: clear model and `row_map`, then add all items, then clear flag. Remove old client-side `_apply_filters` row-hiding logic.
- **Depends on:** Task 4
- **Acceptance:** Manual: filter processes by name/who/status. Results update without duplicates or leftover rows. Clearing filters shows all processes again.

### PublicationsBrowser

#### Task 6: Worker: Add set_filters to PublicationMonitorWorker
- **Estimate:** ~15 lines
- **Files:** `rana_qgis_plugin/workers/persistent.py`
- **Description:** Add `set_filters(filters: dict)` method to `PublicationMonitorWorker`. Method stores filters locally and clears `self.monitored_publications` cache. Update `run()` to pass stored filters to `get_project_publications()`.
- **Depends on:** Task 2
- **Acceptance:** Unit test: calling `set_filters({"search": "bar"})` stores params and empties `monitored_publications`. `run()` passes filters to the API function.

#### Task 7: Loader + signal wiring for publications
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/widgets/publications_browser.py`, `rana_qgis_plugin/widgets/rana_browser.py`, `rana_qgis_plugin/rana_qgis_plugin.py`
- **Description:** Add `update_publication_monitor_filters(filters: dict)` to Loader (calls worker's `set_filters()` then `scheduler.run_task_by_type(PublicationMonitorWorker)`). Add `filters_updated = pyqtSignal(dict)` to PublicationsBrowser, emit on `filters_changed`. Wire signal through RanaBrowser to Loader.
- **Depends on:** Task 6
- **Acceptance:** Manual: changing a filter in PublicationsBrowser triggers the worker to re-fetch with new params.

#### Task 8: PublicationsBrowser: Full-refresh on filter change
- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/widgets/publications_browser.py`
- **Description:** Add `_pending_full_refresh` flag, set to True when `filters_changed` fires. In `add_items`, if flag is set: clear model and `row_map`, then add all items, then clear flag. Remove old client-side `_apply_filters` row-hiding logic.
- **Depends on:** Task 7
- **Acceptance:** Manual: filter publications by name/who. Results update without duplicates or leftover rows. Clearing filters shows all publications again.

### ProjectsBrowser

#### Task 9: ProjectsBrowser: Server-side filtering, pagination, sorting
- **Estimate:** ~80 lines
- **Files:** `rana_qgis_plugin/widgets/projects_browser.py`
- **Description:** Remove `self.tenant_projects` and `self.filtered_projects` local caches. Make `_apply_filters()` call `get_tenant_projects()` with `search` and `project_user_id` params. Pass `ordering` param on sort header click. Pagination fetches from API with `limit`/`offset`. Any filter or sort change resets to page 1. Populate who combo from current page results. Use API response `total` for pagination display.
- **Depends on:** Task 2
- **Acceptance:** Manual: filter projects by name/who -- results come from server. Sort by column header -- triggers re-fetch with ordering param. Paginate -- each page is a fresh API call. Who combo shows users from current page only.

#### Task 10: Add "All" reset option to combo filters in FilterBar
- **Estimate:** TBD
- **Files:** `rana_qgis_plugin/widgets/filter_bar.py`
- **Description:** Add a reset option (e.g. "All") at the top of combo filters so users can explicitly deselect a filter without clearing text. Details to be fleshed out during implementation.
- **Depends on:** None
- **Acceptance:** TBD

#### Task 11: Fix case-sensitive name sorting in ProjectsBrowser
- **Estimate:** TBD
- **Files:** TBD -- depends on whether this is fixable in the API or requires a workaround
- **Description:** `order_by=name` on the projects API sorts case-sensitively (z-a before Z-A). Options: raise with backend to fix the API, or work around client-side if feasible (e.g. post-sort the current page). Details to be investigated.
- **Depends on:** None
- **Acceptance:** Sorting by project name is case-insensitive (e.g. "apple" appears before "Banana")


- FilesBrowser retains client-side filtering (no API support) -- no changes needed
- If flicker is noticeable on processes/publications after tasks 5/8, revisit with diff-based model update
- Open questions: exact `ordering` param format (check API docs during task 9)

## Testing Checkpoints
- After Task 1: all browsers work with debounced filter bar
- After Task 5: processes browser fully server-side filtered
- After Task 8: publications browser fully server-side filtered
- After Task 9: projects browser fully server-side filtered/sorted/paginated

## Progress
- [x] Task 1: FilterBar: Replace QLineEdit with DebouncedSearchBox
- [x] Task 2: API functions: Add filter/pagination params
- [x] Task 3: Worker: Add set_filters to ProjectJobMonitorWorker
- [x] Task 4: Loader + signal wiring for processes
- [x] Task 5: ProcessesBrowser: Full-refresh on filter change
- [x] Task 6: Worker: Add set_filters to PublicationMonitorWorker
- [x] Task 7: Loader + signal wiring for publications
- [x] Task 8: PublicationsBrowser: Full-refresh on filter change
- [x] Task 9: ProjectsBrowser: Server-side filtering, pagination, sorting
- [x] Task 10: Add "All" reset option to combo filters in FilterBar
- [ ] Task 11: Fix case-sensitive name sorting in ProjectsBrowser (pending backend fix)
