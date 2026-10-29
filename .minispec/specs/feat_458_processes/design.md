---
feature: processes-browser-port
status: planned
created: 2026-10-29
decisions:
  - 20261029-1105-processes-window-container
  - 20261029-1106-processes-background-polling
  - 20261029-1107-processes-table-filters-details
  - 20261029-1108-processes-simulation-cancel
  - 20261029-1300-processes-notify-on-process-start
---

# Feature Specification: Processes Browser

**Feature Branch**: `feat_458_processes`  
**Created**: 2026-10-29  
**Status**: Designed  
**Input**: Port the legacy ProcessesBrowser to the current data-item architecture, with a project context-menu entry, jobs table, details on selection, legacy filters, and a suitable window and background-update approach.

## Overview

Add a **Processes** action to each Rana project data item's context menu. It opens a per-project floating `QDockWidget`, which users can leave as a free window or dock into QGIS. The window shows live-updating project jobs, the legacy name/contributor/status filters, a logs details panel for the selected job, and a cancel action for eligible simulation jobs.

Reuse current components where possible: `FilterBar`, `get_project_jobs`, `QAbstractTableModel`/`QTreeView`, `QgsTask`, and the existing 3Di `ThreediCalls` wrapper. Do not copy the legacy `QThreadPool` scheduler pattern.

## User Scenarios & Testing

### User Story 1 - Open project processes (Priority: P1)

As a QGIS user, I want to open a project's processes from its browser context menu so I can monitor jobs without leaving QGIS or blocking work in the map canvas.

**Independent Test**: Right-click a Rana project, choose **Processes**, and verify a window opens without blocking interaction with QGIS.

**Acceptance Scenarios**:

1. **Given** a project data item, **When** I choose **Processes**, **Then** a floating window opens with that project's name in its title.
2. **Given** the Processes window is open, **When** I interact with the QGIS canvas or browser, **Then** QGIS remains usable.
3. **Given** a Processes window for a project is already open, **When** I choose **Processes** for that same project again, **Then** the existing window is raised rather than creating a duplicate.
4. **Given** windows for two different projects, **When** both are opened, **Then** each displays its own project's jobs and can independently float or dock.

### User Story 2 - Find and monitor jobs (Priority: P1)

As a user, I want to filter and monitor a project's jobs so I can find a particular process and see its current state.

**Independent Test**: Open the window for a project with jobs; filter by name, contributor, and status; verify the table refreshes and updates on its polling interval.

**Acceptance Scenarios**:

1. **Given** the Processes window is open, **When** a poll completes, **Then** the table reflects the latest jobs without overlapping fetches.
2. **Given** jobs are displayed, **When** I set a name, contributor, or status filter, **Then** matching results are fetched promptly using the corresponding API filter.
3. **Given** a matching job is selected, **When** its name link is activated, **Then** its Rana web job page opens in the system browser.
4. **Given** a fetch fails, **When** the task completes, **Then** the user receives the existing API/connection error feedback and the UI remains usable.

### User Story 3 - Read job logs (Priority: P2)

As a user, I want to select a job and read its logs below the table so I can inspect process details without switching to the web app.

**Independent Test**: Select different jobs and verify the details panel displays the corresponding logs; verify empty logs and fetch errors have understandable states.

**Acceptance Scenarios**:

1. **Given** a job is selected, **When** its logs are fetched, **Then** timestamp, level, message, and optional exception are displayed in a read-only panel below the table.
2. **Given** no job is selected, **When** the panel is shown, **Then** the details area prompts the user to select a job or is empty.

### User Story 4 - Cancel a simulation job (Priority: P2)

As a user, I want to cancel an eligible running simulation job after confirmation so I can stop a simulation that should no longer continue.

**Independent Test**: Use a running simulation-tracker job with a `simulation_id`; confirm cancellation and verify the UI reports the pending state and a later poll reflects the server state.

**Acceptance Scenarios**:

1. **Given** a running job has `inputs.simulation_id`, **When** its row is displayed, **Then** a cancel affordance is available.
2. **Given** a running job has no `inputs.simulation_id`, **When** its row is displayed, **Then** no cancel affordance is shown.
3. **Given** the user activates cancel, **When** they reject the confirmation, **Then** no shutdown request is sent.
4. **Given** the user confirms cancellation, **When** the 3Di shutdown action succeeds, **Then** the row optimistically shows `cancelling` until a later poll reports the server state.
5. **Given** cancellation fails, **When** the request returns an error, **Then** the user is informed and the row is corrected by a subsequent poll.

### User Story 5 - Point the user at Processes when starting a tracked action elsewhere (Priority: P2)

As a user who just started a model creation or simulation from the schematisation revision history dialog, I want to be guided to the Processes window to watch it, instead of only getting an external web link.

**Independent Test**: Start a model creation (or a simulation) from the revision history dialog with a Processes dock already open (floating, then docked), and again with no dock open; verify each case behaves as described below.

**Acceptance Scenarios**:

1. **Given** a floating Processes dock for the project is already open, **When** a model/simulation tracker process is started, **Then** the dock is raised to the front and the new job row(s) are selected and temporarily highlighted once visible, with no blocking popup.
2. **Given** a docked Processes dock for the project is already open, **When** a process is started, **Then** its tab is brought to the front (if tabbed) and a brief message-bar note points to it, and the new job row(s) are highlighted once visible.
3. **Given** no Processes dock for the project is open, **When** a process is started, **Then** the user is asked whether to open the Processes window; accepting opens it and highlights the new job(s); declining shows no further popup — the unconditional, link-free "started" message already given covers that case.
4. **Given** a highlighted job is excluded by the panel's current filters, **When** the fetch used to find it completes, **Then** nothing crashes and the job simply isn't visually found (documented limitation, not auto-fixed by clearing filters).

## Requirements

### Functional Requirements

- **FR-001**: The Rana project data-item context menu MUST include a **Processes** action.
- **FR-002**: The action MUST open a non-modal, per-project floating `QDockWidget` that the user can dock into QGIS.
- **FR-003**: Reopening the action for a project with an existing Processes dock MUST raise/activate that dock; different projects MUST have independent docks.
- **FR-004**: The jobs table MUST show job name, process name, contributor, start time, and status/progress.
- **FR-005**: The job name MUST retain the legacy link behavior, opening the job's Rana web page.
- **FR-006**: The UI MUST provide name, contributor, and status filters using the existing `FilterBar` and supported project-jobs API parameters.
- **FR-007**: The status filter MUST include the legacy options: scheduled, pending, running, completed, failed, cancelled, crashed, paused, and cancelling.
- **FR-008**: Selecting a row MUST display that job's logs beneath the table, including timestamps, levels, messages, and available exceptions.
- **FR-009**: Jobs MUST refresh every 10 seconds while the window is open; fetches MUST not overlap. Filter changes MUST trigger a prompt fetch.
- **FR-010**: Hiding/closing a dock MUST stop its timer and prevent late task completion from updating a hidden panel. Reopening its context-menu action MUST raise the same dock and resume polling; destroying the dock MUST remove its project registry entry. Polling tasks are not user-cancellable; an in-flight request may finish after hide/close, but its result MUST be ignored.
- **FR-011**: Job polling MUST use a one-shot `QgsTask` pattern consistent with current task usage, not the legacy persistent `QThreadPool` scheduler.
- **FR-012**: A cancel action MUST be available only for running jobs whose inputs contain `simulation_id`; it MUST ask for confirmation and issue the 3Di simulation shutdown action.
- **FR-013**: Cancellation MUST show a pending `cancelling` state after a successful request, with the next poll authoritative for final status.
- **FR-014**: API/task failures MUST be reported through current error/communication patterns without leaving the window unusable.
- **FR-015**: Starting a model-creation or simulation-tracker process from `SchematisationRevisionHistoryDialog` MUST point the user at that project's Processes window: raise-and-activate if floating, raise-and-note if docked, or ask-to-open if not open. The pre-existing external-link popup (`show_process_url_popup` and the equivalent in `start_simulation_tracker_process`) is removed entirely, including on decline — it is considered obsolete, not a fallback to preserve.
- **FR-016**: Once the Processes window for that project is visible, the job(s) just started MUST be selected and temporarily highlighted once they appear in a refreshed fetch.

### Key Entities

- **Project**: Rana project identified by `id`, with `name` and `slug` used for title and links.
- **Job**: API job identified by `id`, including its name, process metadata, creator, state/progress, start time, and optional inputs. `inputs.simulation_id` enables simulation-only cancellation.
- **Job log entry**: Log record associated with a job, containing timestamp, level, message, and optional exception.

## Components and API

### `RanaProjectDataItem`

Add a **Processes** `QAction` following the existing project context-action pattern in `rana_qgis_plugin/data_items/project_item.py`.

### `JobData` and `ProcessProgressBar` (reused, recreated in native code)

Legacy defines `JobData` (a dataclass parsing a job API response) and `ProcessProgressBar` (a status-colored progress bar) with no legacy-specific coupling — `JobData` depends only on `utils/time.convert_to_numeric_timestamp` (already current/non-legacy), and `ProcessProgressBar` is a 10-line subclass of `ColoredProgressBar` from `threedi_mi_utils.ui`, a package already used in current non-legacy code (`communication.py`). Recreate both in native modules as-is (not imported from `rana_qgis_plugin.legacy`, per the architecture boundary in `20260928-1755-legacy-migration-boundary`): `JobData` in `rana_qgis_plugin/widgets/jobs_models.py` (pure data model, cheaply unit-testable), `ProcessProgressBar` in `widgets/processes_panel.py`. Only legacy's row-management layer around them (`QStandardItemModel` + manually-reindexed `row_map`) is being replaced — see below.

Also recreate these small pieces of legacy logic as-is, since each is independent of the `row_map`/`QStandardItemModel` flaw and already correct:
- `job_can_be_cancelled(job: JobData, simulation_tracker_process_id: str | None) -> bool` in `widgets/jobs_models.py`: `job.status == "running" and job.process_id == simulation_tracker_process_id` — legacy's actual eligibility check (`ProcessesBrowser.add_item`/`.update_state_for_job`), not an `inputs.simulation_id` presence heuristic. `simulation_tracker_process_id` is resolved once via the existing `get_process_id_for_tag("simulation_tracker")` (`utils/api.py:808`, already non-legacy); legacy's `inputs["simulation_id"]` is read separately, only as the 3Di action payload.
- `build_job_link_html(job: JobData, project_slug: str) -> str` in `widgets/jobs_models.py`: legacy's `update_job_link` URL/fallback logic (`{base_url}/{tenant}/projects/{slug}?tab=2&job={id}` as a link when `job.process_id` is set, else plain styled text) — pure string building.
- `apply_job_progress(progress_bar: ProcessProgressBar, job: JobData) -> None` in `widgets/processes_panel.py`: legacy's `update_pb_progress` body (`setValue`, `setMaximum`, `setFormat(job.progress_str())`, `set_status(job.status)`).
- The Name column uses a single-line `QLabel` index widget for the job link and elides at the available column width. The model returns empty display text for that cell so the default delegate does not paint duplicate text beneath the label. Name cells do not wrap; table rows use uniform heights.

Explicitly not reused, because this design's prior decisions already make the equivalent legacy complexity unnecessary:
- `row_map` (the flaw being replaced — see `JobsTableModel` below).
- `update_project()` (resets the model when legacy's single shared browser widget switches projects) — not needed; each dock is bound to one project for its entire lifetime.
- `cancelled_sim_map` + `on_simulation_cancel_requested`/`on_simulation_cancelled` (bookkeeping to bridge an async cancel-confirmation signal) — not needed; cancellation here is a synchronous call, so the `cancelling` state is set inline, no later signal to bridge.
- `_pending_full_refresh` (defers a model clear until the next async worker push after a filter change) — not needed; each poll/filter-change already does one synchronous full re-fetch and reconciliation.
- `fetch_simulation_status(simulation_pk)` in legacy's cancel handler — its return value is unused in legacy; not ported.

### `ProcessesPanel` and table model

Create a container-agnostic `ProcessesPanel(QWidget)` with a `FilterBar`, a `QTreeView` backed by `JobsTableModel(QAbstractTableModel)`, and a read-only logs details area below the table. `JobsTableModel` replaces legacy's `QStandardItemModel` + `row_map` (which reindexes every stored row position by hand on each insert) with id-based reconciliation on each poll. A normal scheduled poll must not reset or redraw the entire table: insert rows for new job IDs, update only changed existing jobs, remove IDs absent from the latest response (including when the active server-side filter excludes them), and use targeted row moves to follow the current API response order. Preserve selection by job ID when the selected job remains in the result. Do not expose user-configurable sorting or re-sort client-side; the API order is authoritative and places the newest jobs first according to its response behavior. Reuse `JobData` for each row's parsed data and `ProcessProgressBar` for the status cell's progress rendering, and `build_job_link_html` for the single-line Name cell (a `QLabel` cell widget, same technique as the Status cell, not a plain delegate-painted column — preserves the clickable-link behavior).

Cancel button state is a transition, not a disable/re-enable pair: disable the affordance the moment cancel starts; on success, set the job's status to `"cancelling"` in the model (the affordance naturally disappears via `job_can_be_cancelled`'s `status == "running"` check, rather than being confusingly re-enabled); on failure, re-enable it and show the error. The cancel call itself (`ThreediCalls.create_simulation_action`) is synchronous — short, single, explicit, already gated by a confirmation dialog, not worth `QgsTask` overhead (see `20261029-1108-processes-simulation-cancel`).

Wire the dynamic "who" filter combo the same way `ProjectsSelectionDialog.populate_contributors` already wires its own contributor combo (legacy's equivalent: `_repopulate_who_combo`): scan the currently-loaded rows' `job.user`, dedupe, build `(name, id, avatar)` tuples, call `filter_bar.set_combo_items`.

Use the existing `ContributorAvatarsDelegate` where the job creator data is compatible; otherwise render a readable contributor name without requiring a new avatar subsystem.

### Dock lifetime and deduplication

Maintain open docks by project ID on `Loader` (alongside task references). A plain opening helper raises an existing dock for the same project or creates a new dock and `ProcessesPanel`. Remove the entry when the dock is destroyed/closed. Use the project name in the dock title. The dock starts floating and remains user-dockable.

### Background polling

Each `ProcessesPanel` owns its 10-second `QTimer`, current one-shot `JobsFetchTask`, and fetch completion handling. The panel submits a non-user-cancellable task to QGIS's task manager and retains its task reference; Loader does not register these panel-owned poll tasks in `active_tasks`. A poll tick skips itself while a fetch is active (don't pile up). If filters change during a fetch, retain the latest filter snapshot and start one follow-up fetch when the active request completes; intermediate changes coalesce. Discard a completed result if it used stale filters. This avoids mutating request parameters or relying on task cancellation to interrupt a synchronous network call, while still fetching promptly instead of waiting for the next poll tick. Filtering stays server-side (`get_project_jobs(project_id, params=current_filters)`) — matching legacy's own approach (`Loader.update_job_monitor_filters` also builds server-side params and forces an immediate re-poll) — rather than caching one unfiltered page and filtering it client-side, which would silently miss jobs older than that cached page once a project has more than the `limit=100` most recent jobs. Loader owns the per-project dock registry and instructs each panel to stop polling during plugin shutdown. The panel also stops its timer while hidden and resumes it when shown again. An in-flight request may finish after hide or shutdown; its result must be ignored if the panel is hidden, stopped, or destroyed. Destroying the dock removes its registry entry.

### Notifying from existing process-start flows (`Loader.point_user_to_processes`, `ProcessesPanel.highlight_jobs`)

`SchematisationRevisionHistoryDialog`'s `create_model` and `Loader.start_simulation_tracker_process` (reached via `start_simulation` → `start_simulations` → the `initializing_simulations_finished` completion lambda) each start one or more Rana tracker jobs today and show a blocking external-link popup. That popup is considered obsolete and is removed entirely (not kept as a fallback): `show_process_url_popup` (`version_history_dialog.py`) is deleted, and the `<a href>`-building `links` list in `start_simulation_tracker_process` is removed. `Loader.point_user_to_processes(project, job_ids, error_signals, parent=None) -> None` takes over pointing the user at the window:
- Dock open and floating: `dock.raise_()` + `dock.activateWindow()`.
- Dock open and docked: `dock.raise_()` (brings a tabified dock's tab forward; a no-op if already the sole visible panel) + `communication.bar_info("See the Processes panel for progress.")`.
- Dock not open: `communication.ask(...)` to open it; on accept, `open_processes_dock(...)`; on decline, nothing further happens.
- Either open path then calls `dock.widget().highlight_jobs(job_ids)`.

Each caller gives its own unconditional, link-free "started" confirmation before calling `point_user_to_processes`, independent of its outcome, so declining never leaves the user without feedback: `create_model` already gets this from `start_model_tracker_process`'s existing `bar_info("Revision uploaded; model creation started.")` (no change needed there); `start_simulation_tracker_process` gains an equivalent `bar_info(...)` once tracker jobs are created, replacing its removed popup. `point_user_to_processes` has no return value for callers to branch on — there's nothing left to fall back to.

`ProcessesPanel.highlight_jobs(job_ids: list[str])`: records the requested ids; if a fetch is already in flight (e.g. the dock's own just-triggered initial fetch), waits for it rather than starting a redundant second one; otherwise triggers an immediate fetch via the same fetch-now/coalescing path filter changes use. Once a fetch completes, checks the requested ids against the refreshed rows: if found, selects + scrolls to them and calls `JobsTableModel.set_highlighted_job_ids(...)` (temporary `Qt.BackgroundRole` override, cleared via a single-shot 30-second `QTimer`). If a job isn't present yet (e.g. excluded by an active filter), nothing further happens for v1 — filters are not auto-cleared.

Scope: only the History dialog's `create_model` and `start_simulation` chain are wired to this. The initial-revision-upload flow's own `start_model_tracker_process` call (`loader.py:892-902`) already discards its response and shows no popup at all today — a pre-existing gap, not folded into this feature.

### API

- Reuse `get_project_jobs(project_id, params)` from `rana_qgis_plugin/utils/api.py` for polling and filters (`search`, `created_by`, `status`).
- Reuse `get_process_id_for_tag("simulation_tracker")` from `rana_qgis_plugin/utils/api.py` (already non-legacy) to resolve the process id used by `job_can_be_cancelled`.
- Add `get_job_logs(job_id, params=None)` in `utils/api.py`, following the current API helper patterns; use the POC's logs endpoint and limit behavior as reference.
- Fetch logs on row selection on demand. This is designed as synchronous to avoid adding a second task abstraction for a one-off user action; validate latency/API behavior during implementation and revisit if it causes noticeable UI stalls.
- Use current 3Di simulation API wrapper (`ThreediCalls`) for the simulation shutdown action; do not introduce a generic Rana job-cancel API.

## Edge Cases

- The project has no jobs, or filters match no jobs.
- Selected job disappears from a later poll; clear or update the details panel and selection consistently.
- A poll is still active when filters change, the window closes, or QGIS shuts down; filter changes coalesce to one latest-filter follow-up fetch, and closed/hidden panels ignore completed results.
- API connection or fetch failure occurs during polling or logs retrieval.
- A running non-simulation job lacks `simulation_id`; it must not expose cancel.
- Job input/state/log fields are missing or null; rendering must use safe fallbacks.
- The user opens windows for multiple projects; each poll is scoped to its own project and closing one does not affect the others.
- A synchronous logs request is slow; implementation should measure actual behavior and use a `QgsTask` if it violates responsive-UI expectations.
- A model/simulation start happens while no Processes dock is open and the user declines to open one — no popup is shown as a fallback; the unconditional "started" message given before this check already covered feedback.
- A model/simulation start happens while a fetch is already in flight for that project's panel (e.g. its own just-triggered initial fetch) — the highlight request waits for that fetch rather than starting a redundant second one.
- The job(s) just started are excluded by the panel's currently active filters — highlighting silently finds nothing further; filters are not auto-cleared.
- `dock.raise_()` is called on a docked, non-tabified panel that's already the frontmost/only visible content — visually a no-op; the accompanying `bar_info` message is the only cue in that case.

## Out of Scope

- Generic cancellation for non-simulation jobs.
- Unsolicited background notifications when a job starts or finishes while no related action was just taken by the user in the current session (narrowed by `20261029-1300-processes-notify-on-process-start`: a direct, same-session consequence of the user starting a model/simulation from the history dialog is in scope; a general "tell me whenever any job changes state" watcher is not).
- Wiring the initial-revision-upload flow's own `start_model_tracker_process` call (`loader.py:892-902`, which already shows no popup today) into this notification path.
- Starting new processes from this window.
- An aggregate all-projects jobs dashboard.
- Job inputs or additional metadata in the details panel (logs only for this feature).
- Persisting dock position/floating state across QGIS sessions.

## Success Criteria

- The project context action opens or raises the correct per-project dock without blocking QGIS.
- The table refreshes at the agreed interval, supports all three filters, and never starts overlapping polls.
- Selecting a row shows that job's logs; web links open the corresponding Rana job page.
- Only eligible running simulation jobs can be cancelled, and cancellation errors are communicated.
- Hiding a dock stops its polling, reopening resumes it, and destroying one project's dock does not affect another project's dock.
- Starting a model/simulation from the revision history dialog points the user at that project's Processes window per its current state (floating/docked/not open); the external-link popup no longer appears in any of these flows.

## Manual UI Testing

Right-click a Rana project → **Processes**; verify the floating dock, project title, reuse-and-raise behavior, multi-project independence, docking/undocking, table columns, and link behavior. With jobs available, test each filter, 10-second updates, row-selection logs, refresh, empty/error states, and close behavior. Confirm long job names remain single-line and elide when the Name column is narrow. For cancel, confirm both a running simulation job with `simulation_id` and a running non-simulation job without it; verify confirmation, success/error feedback, and server-confirmed status on the next poll.

For the notification integration: from the schematisation revision history dialog, start a model creation and a simulation with the project's Processes dock (a) open and floating, (b) open and docked, and (c) not open, confirming the behavior described in User Story 5 for each case; also confirm declining to open (case c) shows no popup — only the unconditional "started" message bar note from before the prompt.
