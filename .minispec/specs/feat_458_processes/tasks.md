---
feature: feat_458_processes
status: planned
created: 2026-10-29
chunk_size: adaptive
total_tasks: 11
estimated_lines: 565
---

# Tasks: Processes Browser (port using data items)

**Input**: `.minispec/specs/feat_458_processes/design.md`
**Branch**: `feat_458_processes`

## T001: `get_job_logs` API helper

- **Estimate:** ~20 lines
- **Files:** `rana_qgis_plugin/utils/api.py`
- **Description:** Add `get_job_logs(job_id: str, params: Optional[dict] = None) -> dict`, using `simple_fetch` so HTTP failures raise `RanaFetchError` instead of being confused with an empty result. Apply the same explicit failure behavior to `get_project_jobs`. Use the POC's logs endpoint/limit as reference (`rana-plugin-poc/utils_api.py:431`).
- **Depends on:** None
- **Acceptance:** Both helpers return response dictionaries on success and raise `RanaFetchError` on HTTP/API failure; `RanaFetchError` includes HTTP status when available.
- **Evidence:** README Docker unit suite passes (503 passed, 2 skipped). Live endpoint verification was not performed.

## T002: `JobsFetchTask` [P]

- **Estimate:** ~45 lines incl. tests
- **Files:** `rana_qgis_plugin/workers/rana_jobs.py` (new), `tests/workers/test_rana_jobs.py` (new)
- **Description:** One-shot `QgsTask` shaped like `HistoryFetchTask`/`ScenarioResolveTask`: takes a project ID and optional filter params, calls `get_project_jobs`, and stores `.result`/`.error`; no custom signals. Used by `ProcessesPanel`'s poll timer.
- **Depends on:** None
- **Acceptance:** Task stores the `get_project_jobs` result or raised exception, and snapshots filter params at construction. Polling task is not user-cancellable; stale results are discarded by the panel.
- **Evidence:** `pytest tests/workers/test_rana_jobs.py -q` passes.

## T003: `JobData` + `job_can_be_cancelled` + `build_job_link_html`, recreated from legacy [P]

- **Estimate:** ~55 lines incl. tests
- **Files:** `rana_qgis_plugin/widgets/jobs_models.py` (new), `tests/widgets/test_jobs_models.py` (new)
- **Description:**
  - Recreate `JobData` as-is from `legacy/widgets/processes_browser.py:54-94` (pure dataclass; only dependency is `utils/time.convert_to_numeric_timestamp`, already native).
  - `job_can_be_cancelled(job: JobData, simulation_tracker_process_id: str | None) -> bool`: `job.status == "running" and job.process_id == simulation_tracker_process_id` — legacy's actual eligibility check (`ProcessesBrowser` lines 217, 287), not an `inputs.simulation_id` presence heuristic.
  - `build_job_link_html(job: JobData, project_slug: str) -> str`: legacy's `update_job_link` URL/fallback logic, as a pure function.
- **Depends on:** None
- **Acceptance:** Unit tests cover: eligibility true only for running + matching process id; link HTML includes the job URL when `process_id` is set, plain text otherwise.
- **Evidence:** `pytest tests/widgets/test_jobs_models.py -q` passes — pure Python assertions, no `qgis_application` fixture needed.

## T004: `ProcessProgressBar` + `apply_job_progress` + `WordWrapDelegate` + `JobsTableModel`

- **Estimate:** ~95 lines incl. tests
- **Files:** `rana_qgis_plugin/widgets/utils_delegates.py`, `rana_qgis_plugin/widgets/processes_panel.py` (new), `tests/widgets/test_processes_panel.py` (new)
- **Description:**
  - Recreate `ProcessProgressBar` as-is (`legacy/widgets/processes_browser.py:22-33`), importing `ColoredProgressBar` from `threedi_mi_utils.ui` directly (already a native dependency, see `communication.py`).
  - `apply_job_progress(progress_bar, job)`: port `update_pb_progress`'s body as-is.
  - Add `WordWrapDelegate` to `widgets/utils_delegates.py` (alongside the existing `ContributorAvatarsDelegate`) — recreate the legacy wrapping paint/size behavior. Since the new `QAbstractTableModel` replaces legacy's `QStandardItem`, ensure the Name column returns the real job name for `Qt.DisplayRole`; the delegate's `sizeHint()` must measure that text rather than an empty value.
  - `JobsTableModel(QAbstractTableModel)`: the actual new piece. Reconciles rows by job id on each refresh using targeted inserts, updates, moves, and removals rather than resetting the whole model. Preserve the order returned by the API (newest jobs first per the endpoint response); do not add client-side sorting. Preserve selection by job id.
- **Depends on:** T003 (`JobData`, `job_can_be_cancelled`)
- **Acceptance:** Normal refreshes update the model incrementally without a full reset: new ids are inserted in API response order, changed existing jobs update their rows, and ids absent from the returned (possibly filtered) result are removed. Row moves follow API order changes; no user-configurable sorting is added. Selection is preserved by job id when its row remains. `ProcessProgressBar.set_status` color-maps match legacy's three buckets (finished/running/failed).
- **Evidence:** `pytest tests/widgets/test_processes_panel.py -q` passes, covering row insert/update/removal, selection preservation, API-order changes, and delegate size calculation from Name display text. Manual: a long Name is displayed on one line and elides when the column is narrow.

## T005: `ProcessesPanel` core — filters + table + polling + "who" combo

- **Estimate:** ~90 lines
- **Files:** `rana_qgis_plugin/widgets/processes_panel.py`
- **Description:** Wire `FilterBar` (name/who/status, same config as legacy), `QTreeView` + `JobsTableModel`, single-line elided Name and metadata columns, and flexible Name/Process name widths. The panel owns its 10s `QTimer` and current `JobsFetchTask`; submit one-shot tasks to QGIS's task manager and retain the current task reference (do not register panel poll tasks in Loader's `active_tasks`). Fetch with `get_project_jobs(project_id, params=current_filters)` (server-side filtering, matching legacy). Poll ticks skip while a fetch is in flight. Filter changes during a fetch retain the newest filter snapshot and trigger one follow-up fetch when the current request completes; discard stale results. Hidden or stopped panels ignore in-flight results. Loader instructs panels to stop polling on plugin shutdown. Wire the "who" combo the same way `ProjectsSelectionDialog.populate_contributors` does: scan currently-loaded rows' `job.user`, dedupe, `filter_bar.set_combo_items`.
- **Depends on:** T002, T004
- **Acceptance:** Opening/showing the panel starts polling; hiding or Loader shutdown stops its timer. A filter change triggers an immediate re-fetch without waiting for the next tick. If a fetch is active, only one follow-up starts after it completes, using the latest filters; the stale result is discarded and requests do not overlap. Poll fetch tasks are retained by the panel and not exposed as user-cancellable tasks.
- **Evidence:** `docker compose run --rm qgis pytest tests/widgets/test_processes_panel.py tests/widgets/test_jobs_models.py tests/workers/test_rana_jobs.py -q --tb=short` passes. Manual UI verification remains part of T008's dock test: confirm polling at ~10s, prompt name-filter fetches (bounded by FilterBar's existing 400ms debounce), contributor/status filters, and hide/show polling lifecycle.

## T008: Loader dock hosting + dedup

- **Estimate:** ~55 lines
- **Files:** `rana_qgis_plugin/loader.py`
- **Description:** `Loader.process_docks: dict[str, QDockWidget]` (alongside `active_tasks`). `Loader.open_processes_dock(project, error_signals, parent=None)`: raise/activate an existing dock for `project["id"]`, or create a new `QDockWidget` (floating by default, titled with the project name) hosting a `ProcessesPanel`, register via `self.communication.iface.addDockWidget(...)`. Panel visibility controls its own polling timer (stop while hidden, resume when shown); Loader shutdown calls `stop_polling()` on registered panels. Remove the registry entry on actual dock destruction.
- **Depends on:** T005
- **Acceptance:** Reopening for the same project raises the existing dock (no duplicate); different projects get independent docks; hide/show correctly stops/resumes polling.
- **Evidence:** `docker compose run --rm qgis pytest tests/loader/test_processes_docks.py tests/loader/test_shutdown.py -q --tb=short` passes. Manual UI test after T009 makes the dock reachable: open/raise same project, open a second project, dock/float, and hide/reopen to verify polling resumes independently.

## T009: Context menu action

- **Estimate:** ~30 lines incl. test
- **Files:** `rana_qgis_plugin/data_items/project_item.py`, `tests/data_items/test_project_item.py` (new)
- **Description:** Add a **Processes** `QAction` to `RanaProjectDataItem.actions()`, mirroring the existing "Open project on web" action (same file, lines 63-72). Wire to `self.loader.open_processes_dock(self.project, self.error_signals)`.
- **Depends on:** T008
- **Acceptance:** Right-clicking a project shows **Processes**; triggering it calls `Loader.open_processes_dock` with the right project.
- **Evidence:** `docker compose run --rm qgis pytest tests/data_items/test_project_item.py -q --tb=short` passes. Manual: right-click a real project in the browser panel, select **Processes**, and verify the project dock opens.

## T007: Cancel action wiring

- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/widgets/processes_panel.py`
- **Description:** Resolve `simulation_tracker_process_id` once via `get_process_id_for_tag("simulation_tracker")`. Show the cancel affordance only when `job_can_be_cancelled(job, simulation_tracker_process_id)`. On click: confirm dialog, disable the affordance, call `ThreediCalls(get_threedi_api()).create_simulation_action(job.inputs["simulation_id"], name="shutdown")` synchronously (no `QgsTask` — short, single, explicit, already confirmation-gated; do not port legacy's unused `fetch_simulation_status` call). On success: set the job's status to `"cancelling"` in the model (the affordance disappears via the eligibility check, not a confusing re-enable). On failure: re-enable the affordance and show the error.
- **Depends on:** T004 (`job_can_be_cancelled`), T005
- **Acceptance:** Cancel only appears for running jobs matching the simulation-tracker process id; confirming calls the 3Di shutdown action; success/failure both leave the row in a correct, non-confusing state.
- **Evidence:** Manual test — a running simulation-tracker job (cancel appears, confirm → cancelling state, next poll confirms) and a running non-simulation job (no cancel affordance).

## T010: `JobsTableModel` highlight state + `ProcessesPanel.highlight_jobs`

- **Estimate:** ~55 lines
- **Files:** `rana_qgis_plugin/widgets/processes_panel.py`
- **Description:**
  - `JobsTableModel`: `set_highlighted_job_ids(job_ids: set[str])` / `clear_highlighted_job_ids()`, backing a `Qt.BackgroundRole` override in `data()` for matching rows; both emit `dataChanged` for the full grid.
- `ProcessesPanel.highlight_jobs(job_ids: list[str])`: records requested ids; if a fetch is already in flight, waits for it (no redundant second fetch); otherwise triggers one immediately via the same fetch-now path T005 uses for filter changes. On that fetch's completion, checks requested ids against the refreshed rows — if found, selects + scrolls to them and calls `set_highlighted_job_ids(...)`, clearing it via a single-shot 30-second `QTimer`; if not found (e.g. excluded by an active filter), does nothing further.
- **Depends on:** T004 (`JobsTableModel`), T005 (fetch-now/coalescing machinery)
- **Acceptance:** Highlighting a job id present in the next fetch selects/scrolls/highlights it and the highlight clears after ~30s; a job id absent from the fetch causes no crash and no visible effect.
- **Evidence:** `docker compose run --rm qgis pytest tests/widgets/test_processes_panel.py -q --tb=short` passes, covering row background role and selection/highlight after fetch. Manual: trigger `highlight_jobs` with the dock open and verify matching jobs are selected, scrolled into view, and highlighted for about 30 seconds.

## T011: `Loader.point_user_to_processes` + wiring into Create Model / Start Simulation

- **Estimate:** ~75 lines
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:**
  - `Loader.point_user_to_processes(project: dict, job_ids: list[str], error_signals: ApiErrorSignals, parent=None) -> None`: looks up `self.process_docks.get(project["id"])`; if found, `dock.raise_()` (+ `activateWindow()` if `dock.isFloating()`, else `communication.bar_info("See the Processes panel for progress.")`), then `dock.widget().highlight_jobs(job_ids)`. If not found, `communication.ask(parent, "Processes", "Track progress in the Processes window?")`; on accept, `open_processes_dock(...)` + `highlight_jobs(job_ids)`; on decline, do nothing further — no return value, no fallback popup.
  - Delete the now-obsolete external-link popup entirely rather than keeping it as a fallback: remove `SchematisationRevisionHistoryDialog.show_process_url_popup` outright, and remove the `<a href>`-building `links` list (and the `escape`/`get_rana_processes_url` usage that built it) from `Loader.start_simulation_tracker_process`.
  - `SchematisationRevisionHistoryDialog.create_model`: replace the `self.show_process_url_popup(job_id)` call with `self.loader.point_user_to_processes(self.project, [job_id], self.error_signals, self)`. No new "started" message needed here — `start_model_tracker_process` already gives one unconditionally (`bar_info("Revision uploaded; model creation started.")`).
  - `Loader.start_simulation_tracker_process`: collect `job_ids` in its loop (replacing `links`); once tracker jobs are created, call `communication.bar_info(...)` (e.g. "N simulation(s) started.") **unconditionally**, then call `point_user_to_processes(project, job_ids, error_signals, parent)` — this ordering means declining the open-dock prompt never leaves the user without feedback.
  - Thread `error_signals: ApiErrorSignals` one level further through the existing simulation-start call chain so `start_simulation_tracker_process` has it: `Loader.start_simulation(..., error_signals, parent)` → `Loader.start_simulations(..., error_signals)` → the `initializing_simulations_finished` lambda (`loader.py:237`) → `start_simulation_tracker_process(..., error_signals)`. `SchematisationRevisionHistoryDialog.start_simulation` passes its existing `self.error_signals`.
- **Depends on:** T008 (dock registry/`open_processes_dock`), T010 (`highlight_jobs`)
- **Acceptance:** With a dock open (floating/docked) or not open, starting a model/simulation behaves per `20261029-1300-processes-notify-on-process-start`; no external-link popup appears in any case, including decline.
- **Evidence:** `docker compose run --rm qgis pytest tests/loader/test_simulation.py tests/loader/test_processes_docks.py tests/widgets/test_processes_panel.py -q --tb=short` passes. Manual UI verification remains: test Create Model and Start Simulation with the dock floating, docked, and closed; confirm prompt accept/decline, started message, job selection/highlight, and no link popup.

## T006: Logs details panel

- **Estimate:** ~35 lines
- **Files:** `rana_qgis_plugin/widgets/processes_panel.py`
- **Description:** Row selection triggers a synchronous `get_job_logs` call (no task — single, user-initiated, matches `ProjectsSelectionDialog.fetch_and_populate`'s existing sync-fetch convention) rendered into a read-only text area. Handle empty/no-selection/error states.
- **Depends on:** T001, T005
- **Acceptance:** Selecting a row shows that job's logs (timestamp, level, message, optional exception); deselecting or a disappeared job clears/updates consistently.
- **Evidence:** `docker compose run --rm qgis pytest tests/widgets/test_processes_panel.py -q --tb=short` passes. Manual UI test: select a job with logs, one without logs, trigger a log-fetch error, and deselect/disappear the selected job; verify details update or clear appropriately.

---

## Manual Test Plan (run once T001–T011 are all complete)

1. Right-click a Rana project → **Processes** opens a floating dock titled with the project name; QGIS canvas/other panels remain usable.
2. Click **Processes** again for the same project — the existing dock is raised, not duplicated. Open it for a second project — independent dock, independent polling.
3. Drag the dock onto a QGIS dock area — it docks normally; float it back out.
4. With jobs present: verify name/contributor/status filters each narrow the table, debounced smoothly for the name field; verify the table updates automatically roughly every 10s.
5. Select a job with a long name — confirm the Name stays on one line and elides when the column is too narrow.
6. Select a job — logs appear below the table; select one with no logs and one that errors; confirm reasonable empty/error states.
7. Click a job's name link — opens the Rana web job page in the system browser.
8. Find a running simulation-tracker job — cancel affordance is visible; confirm cancel — row shows `cancelling`, affordance disappears; next poll confirms final state. Find a running non-simulation job — no cancel affordance.
9. Trigger a cancel failure (e.g. temporarily break auth) — affordance re-enables and an error is shown.
10. Hide the dock (don't destroy it) — confirm polling stops (no further network activity); show it again — polling resumes.
11. Close the dock for real — confirm its registry entry is gone (reopening creates a fresh dock, not a resurrected stale one).
12. From the schematisation revision history dialog, with the project's Processes dock **floating and open**: start a model creation — dock is raised to the front, new job row selected/highlighted (clears after ~30s), no popup shown. Repeat for Start Simulation (single and multiple simulations).
13. Same, with the dock **docked and open** (ideally tabbed behind another panel): its tab is brought to the front, a message-bar note appears, the new row(s) are highlighted.
14. Same, with **no dock open**: confirm the unconditional "started" message bar note appears first, then the "track progress in the Processes window?" prompt; accept once (dock opens, job highlighted) and decline once on a separate run — confirm no popup appears either time, only the message bar note from step 1.

## Notes

- Nothing imports from `rana_qgis_plugin.legacy`; `JobData`, `ProcessProgressBar`, `WordWrapDelegate`, `job_can_be_cancelled`, `build_job_link_html`, and `apply_job_progress` are recreated in native modules per the architecture boundary in `20260928-1755-legacy-migration-boundary`, since each is legacy-independent on its own merits (see `20261029-1107-processes-table-filters-details`).
- `WordWrapDelegate` is reused with a one-line fix (also set `name_item.setText(job.name)`) because legacy's own wiring likely never exercises real wrapping — verify by hand in T004's manual check.
- Cancellation is synchronous by design, not a `QgsTask` — short, single, explicit, confirmation-gated action; see `20261029-1108-processes-simulation-cancel` for the full reasoning (including why `CanCancel` task semantics would be the wrong fit here).
- Filtering stays server-side (`get_project_jobs` with filter params on every fetch), matching legacy's own approach, rather than caching one unfiltered page client-side — the latter would silently miss jobs beyond the `limit=100` cached page. See `20261029-1106-processes-background-polling`.
- T011 only wires `create_model` and the `start_simulation` chain. The initial-revision-upload flow's own `start_model_tracker_process` call (`loader.py:892-902`) already discards its response and shows no popup at all today — a pre-existing gap, intentionally not folded into this feature. See `20261029-1300-processes-notify-on-process-start`.
- The external-link popup (`show_process_url_popup` and the `<a href>`-building code in `start_simulation_tracker_process`) is deleted, not preserved as a fallback — it is considered obsolete now that the Processes window exists.
- Out of scope for this task list (see design.md): generic non-simulation cancel, unsolicited background job-finished notifications unrelated to a just-taken action, starting new processes from this window, an all-projects dashboard, job metadata beyond logs in the details panel, persisting dock position across sessions.

## Progress

- [x] T001: `get_job_logs` API helper
- [x] T002: `JobsFetchTask`
- [x] T003: `JobData` + `job_can_be_cancelled` + `build_job_link_html`
- [x] T004: `ProcessProgressBar` + `apply_job_progress` + `WordWrapDelegate` + `JobsTableModel`
- [x] T005: `ProcessesPanel` core — filters + table + polling + "who" combo
- [x] T008: Loader dock hosting + dedup
- [x] T009: Context menu action
- [x] T007: Cancel action wiring
- [x] T010: `JobsTableModel` highlight state + `ProcessesPanel.highlight_jobs`
- [x] T011: `Loader.point_user_to_processes` + wiring into Create Model / Start Simulation
- [x] T006: Logs details panel
