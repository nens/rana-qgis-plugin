---
type: decision
id: 20261029-1106-processes-background-polling
date: 2026-10-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/processes_panel.py
  - rana_qgis_plugin/workers/rana_jobs.py
  - rana_qgis_plugin/loader.py
tags: [processes, polling, qgstask]
participants: [engineer, assistant]
---

# Processes polling: per-window timer and one-shot QgsTask

## Context

Job state changes while the monitor is open, so a one-time fetch is insufficient. Legacy uses a custom `QThreadPool` scheduler and persistent worker, with a documented filter race. Current code uses `QgsTask` for background work, and Loader already tracks active tasks for shutdown.

## Options Considered

### Option 1: Port legacy scheduler

Reuse `ProjectJobMonitorWorker`, `QThreadPool`, and `PersistentTaskScheduler`.
- ✅ Closely resembles legacy behavior.
- ❌ Carries custom scheduler/lifecycle complexity and the known filter update race into the rewrite.

### Option 2: Per-window QTimer plus one-shot QgsTask

Timer schedules a background fetch task every 10 seconds while its panel is open.
- ✅ Uses the current task convention and scopes work to each visible monitor.
- ✅ No global scheduler; filter changes and refresh can trigger immediate fetches.
- ❌ Requires careful handling of filter changes during a fetch and late completion on close.

### Option 3: Polling loop inside a long-running task

Keep one task alive and repeatedly sleep/fetch.
- ✅ Avoids creating a task for each poll.
- ❌ Makes cancellation, filter changes, and UI lifecycle more complicated.

## Decision

Each `ProcessesPanel` owns a 10-second `QTimer`, its current one-shot, non-user-cancellable `JobsFetchTask(QgsTask)`, and fetch completion handling. The panel submits a task to QGIS's task manager and retains its task reference; Loader does not register panel poll tasks in `active_tasks`. A scheduled poll tick **skips** itself while a fetch is already active (don't pile up redundant requests). If filters change or a manual refresh is requested during a fetch, retain the latest filter snapshot and start one follow-up fetch when the active request completes; intermediate changes coalesce. Discard a completed result if it used stale filters. This avoids mutating request parameters or relying on task cancellation to interrupt a synchronous network call, while still fetching promptly instead of waiting for the next poll tick. The panel stops its timer when hidden and resumes when shown. Loader owns the per-project dock registry and instructs each panel to stop polling during plugin shutdown. An in-flight request may finish normally after hiding or shutdown, but callbacks ignore results when the panel is hidden, stopped, or destroyed.

Filtering stays server-side (`get_project_jobs(project_id, params=current_filters)`, same as today), not a client-side cache of an unfiltered page. This matches legacy's own approach: `Loader.update_job_monitor_filters` (`legacy/loader.py:1983-2002`) also builds server-side query params and forces an immediate re-poll rather than waiting for the next scheduled tick — there is no client-side filtering anywhere in legacy either. Server-side filtering remains correct across a project's full job history (bounded to `limit=100` matches, regardless of total job count), whereas caching one unfiltered page and filtering it client-side would silently fail to find jobs older than that cached page once a project has more than ~100 jobs total — a real correctness gap, not just a style choice, so it is not adopted even though it would feel more instantaneous.

Logs retrieval is a single on-demand action and is designed to be synchronous for the first version, consistent with the user's preference to fetch details when selected and the current convention for one-shot dialog fetches. If latency makes this visibly block QGIS, move logs fetching to a task.

## Consequences

### Positive
- ✅ Avoids copying legacy's custom scheduler and race-prone filter state.
- ✅ Monitoring work ends with its window; multiple project windows remain independent.
- ✅ Keeps polling state and task references with the panel that owns the polling UI.

### Negative
- ⚠️ Loader must stop each registered panel's timer during shutdown; the panel itself guards late results after hiding/stopping.
- ⚠️ Synchronous log retrieval may stall the UI if the endpoint is slow; measure during implementation.
- ⚠️ Confirm the API/network client used by `get_project_jobs` is safe to invoke from a QgsTask worker thread before implementation; if not, adapt the fetch boundary rather than moving Qt UI work off the main thread.
- ⚠️ Filter changes during a request wait for it to finish before the follow-up starts; stale results must be recognized and discarded.

## Code References

- Existing task pattern: `rana_qgis_plugin/workers/history.py:HistoryFetchTask`
- Existing task ownership: `rana_qgis_plugin/loader.py:Loader._track_task`
- Current project jobs API: `rana_qgis_plugin/utils/api.py:get_project_jobs`
- Legacy scheduler reference: `rana_qgis_plugin/legacy/workers/persistent.py`
- Legacy filter trigger (validates server-side filtering + immediate re-fetch, same shape as this decision): `rana_qgis_plugin/legacy/loader.py:Loader.update_job_monitor_filters` (lines 1983-2002)

## Related Decisions

- `20261029-1105-processes-window-container`

## Notes

Task success/termination callbacks and UI feedback should follow current QGIS task conventions. No polling continues while a dock is closed.
