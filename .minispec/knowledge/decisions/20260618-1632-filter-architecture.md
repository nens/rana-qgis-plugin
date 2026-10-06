---
id: 20260618-1632-filter-architecture
status: accepted
date: 2026-06-18
---

# Filter Architecture: Workers with set_filters Method

## Context

The backend now supports server-side filtering for projects, processes, and publications. Processes and publications data arrives via persistent workers (`ProjectJobMonitorWorker`, `PublicationMonitorWorker`) that poll on intervals. We need to pass filter parameters to these workers.

## Decision

Workers get a `set_filters(dict)` method that stores filter params locally and clears the tracked-item cache. The Loader gets specific methods (`update_job_monitor_filters`, `update_publication_monitor_filters`) that call the worker's `set_filters` and then `scheduler.run_task_by_type()` to trigger an immediate re-fetch.

Filter changes flow from browser widgets upward via signals through RanaBrowser to the Loader, following the existing signal relay pattern.

## Alternatives Considered

- **Signal from browser directly to worker:** Rejected -- long signal chain and workers don't have a shared interface.
- **Scheduler owns filter state:** Rejected -- workers don't share an interface, adding this to the scheduler conflates responsibilities.
- **Bypass workers for filtered fetches:** Rejected -- would create two data paths and potential for stale/conflicting data.

## Consequences

- Workers remain the single source of data for processes and publications
- Each worker manages its own filter state independently
- Clearing the cache means the next run() treats all returned items as "new", requiring the browser to handle full model rebuilds (via `_pending_full_refresh` flag)
