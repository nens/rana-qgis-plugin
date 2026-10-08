# Feature Specification: Open Scenario Results

**Feature Branch**: `feat_455_open_results`  
**Created**: 2026-08-31  
**Status**: Planned  
**Input**: Port scenario-result downloading and opening from the legacy loader to the current loader and task architecture.

## Overview

Scenario files will use the current `Loader` and `QgsTask` download architecture while preserving the existing result-selection dialog for an individual scenario. Scenario files opened as part of a multi-select or folder operation will use the legacy batch defaults without showing a dialog, and every successfully downloaded scenario will be opened in Rana Results Analysis.

## User Scenarios & Testing

### User Story 1 - Open one scenario interactively (Priority: P1)

As a user, I want to choose which results to download for one scenario and then analyse them in Results Analysis.

**Why this priority**: This preserves the existing single-scenario workflow while moving it out of the legacy loader.

**Independent Test**: Double-click a scenario or choose its `Open in QGIS` action, choose results in the dialog, and verify the selected files are downloaded and the scenario is loaded once in Results Analysis.

**Acceptance Scenarios**:

1. **Given** a ready scenario with 3Di and Lizard results, **when** the user opens it individually, **then** the result-selection dialog is shown.
2. **Given** the user accepts a selection, **when** all selected downloads succeed, **then** Results Analysis loads that scenario directory once.
3. **Given** the user cancels the dialog, **when** the action ends, **then** no download task is submitted.

### User Story 2 - Open scenarios in a batch (Priority: P1)

As a user, I want multi-select and folder-open operations to include scenarios without repeated dialogs.

**Why this priority**: Batch opening is the established QGIS browser workflow and must work consistently for scenarios, vectors, and rasters.

**Independent Test**: Multi-select multiple scenarios, or open a folder containing scenarios, and verify each valid scenario is downloaded and opened in Results Analysis.

**Acceptance Scenarios**:

1. **Given** a batch containing scenarios, **when** it is opened, **then** no result-selection dialog is shown.
2. **Given** a valid scenario in a batch, **when** defaults are applied, **then** raw `results.zip` and the attached `max water depth (file)` result are downloaded.
3. **Given** multiple valid scenarios in one batch, **when** downloads finish, **then** Results Analysis loads each scenario once.
4. **Given** a mixed batch, **when** it is opened, **then** existing vector and raster behavior is unchanged.

### User Story 3 - Receive useful partial-result feedback (Priority: P2)

As a user, I want unavailable scenarios and failed downloads to be reported while other valid batch items continue.

**Why this priority**: Scenario metadata and post-processing availability vary, especially in folders containing unrelated or incomplete scenarios.

**Independent Test**: Include an unavailable or incomplete scenario in a batch and verify a message-bar warning is shown while valid scenarios still complete.

**Acceptance Scenarios**:

1. **Given** missing descriptor metadata, unavailable Lizard results, or no default attached result, **when** a scenario is processed in a batch, **then** it is skipped and the reason is reported in the message bar.
2. **Given** one downloader fails, **when** the batch finishes, **then** the failure is reported and incomplete scenarios are not opened.
3. **Given** Results Analysis is unavailable, **when** a scenario finishes downloading, **then** the user is warned instead of receiving an exception.

## Edge Cases

- A scenario without a configured working directory is skipped or rejected with a message-bar warning, according to the existing results path requirements.
- A scenario that has only raw results is handled by the existing single-scenario fallback; batch default behavior follows the legacy `download_files` rules and skips scenarios without usable Lizard/default-result metadata.
- Existing result files are handled by the existing overwrite policy for interactive result selection; batch mode does not show per-result selection dialogs.
- A repeated scenario request in one batch is deduplicated and loaded once.
- A batch with no valid downloaders reports that nothing can be downloaded and does not submit an empty task.
- A Results Analysis version without the `project` argument receives the existing compatibility fallback and a warning.
- A scenario whose Rana descriptor metadata is incomplete for its linked 3Di simulation requires a live 3Di API call to resolve; that call may be slow or fail (missing/invalid 3Di token, unreachable 3Di backend) and MUST NOT freeze the UI or raise an unhandled exception (see "Threading Considerations").

## Threading Considerations

### `has_3di_simulation` is load-bearing, not just a dialog-visibility flag

`ScenarioInfo.has_3di_simulation` (and the metadata `set_simulation_info_from_threedi()` fills in when the Rana descriptor alone is incomplete — `schematisation_id`, `schematisation_name`, `revision_number`, `simulation_name`) is used for two decisions, not one:

1. Whether `ResultBrowser` is shown at all (only when `has_lizard_results and has_3di_simulation`), vs. a raw-results-only fallback.
2. **Where downloaded files land on disk** — `ResultsDownloadContext.local_dir` branches on `has_3di_simulation`: `True` resolves the 3Di simulation working directory (using the potentially 3Di-filled fields above), `False` falls back to a generic cache-folder path. This branch is evaluated in **both** the interactive and batch/default download paths.

Because of this, `set_simulation_info_from_threedi()` cannot be treated as a cosmetic eager call that can simply be made lazy or skipped before showing the dialog — its result determines both whether the dialog appears and where every subsequent downloader in that flow writes its output. The resolution genuinely needs to happen, and needs to happen correctly, before either branch proceeds.

### Why background resolution is technically possible

Two backends are involved, with different thread constraints:

- **Rana API calls** (`get_tenant_file_descriptor`, `get_tenant_project_files`, `get_frontend_settings`) go through `NetworkManager` → `QgsNetworkAccessManager.instance()`, a main-thread-bound singleton. `RanaDownloader.resolve_url()` already documents this constraint explicitly ("Must be called on the main thread" — `workers/download.py:303-307`).
- **3Di API calls** (`ThreediCalls.fetch_simulation`, `.fetch_3di_model`) use `ThreediApi`'s own HTTP client, independent of Qt's network stack. This already runs safely in a background thread elsewhere in this codebase: `SchematisationGeopackageDownloader.url` (`workers/download.py:432-439`) calls `ThreediCalls(...).download_schematisation_revision_sqlite(...)` from inside `download_file()`, which executes inside `DownloadTask.run()` on the task's background thread.

So `set_simulation_info_from_threedi()`'s 3Di calls can run in a background `QgsTask`. The Rana descriptor fetch and the one-time `get_threedi_api()` resolution must stay on the main thread, same as every other resolution step already in `loader.py` (`_resolve_folder`, `resolve_schematisation`).

### Per-scenario task pipeline

Resolution and download run as two sequential tasks **per scenario**, chained via `taskCompleted`/`taskTerminated` signals — the same chaining idiom `resolve_schematisation()` already uses for its single `DownloadTask` (`loader.py:1093-1106`), with one extra phase inserted before it. This follows the codebase's existing per-item dispatch pattern (`open_items()` already dispatches one `DownloadTask` per file/schematisation independently, even within a batch) rather than introducing a new cross-scenario batching mechanism.

```
Main thread                         ScenarioResolveTask (background)      Main thread (callback)
────────────                        ─────────────────────────────────     ──────────────────────
1. Fetch this scenario's Rana
   descriptor (get_tenant_file_
   descriptor) — same pattern
   as today
2. Construct ScenarioInfo
   (Rana-only, fast; no 3Di
   call triggered by __init__
   anymore)
3. If ScenarioInfo already has
   complete metadata (no 3Di
   lookup needed) → skip the
   task, go straight to step 6
4. Resolve get_threedi_api()
   for this scenario
5. Submit ScenarioResolveTask
   (busy progress bar:
   "Resolving scenario
   details…")
                                ──▶  For this ScenarioInfo:
                                        ThreediCalls(api)
                                        .set_simulation_info_from_threedi()
                                        — mutates the ScenarioInfo object
                                        in place (same object the main
                                        thread already holds a reference
                                        to — same "mutate then read after
                                        completion" idiom as
                                        SchematisationRevisionDownloadContext).
                                        Wrapped in try/except so a 3Di
                                        failure degrades this scenario to
                                        not-linked rather than failing
                                        the task.
                                ◀──  taskCompleted / taskTerminated
                                                                     6. ScenarioInfo is now fully
                                                                        resolved
                                                                     7a. Single item: show
                                                                         ResultBrowser now
                                                                     7b. Batch: apply fixed
                                                                         defaults (decision
                                                                         20260831-1500), skip/
                                                                         report if unusable
                                                                     8. Build ResultsDownloadContext
                                                                        + downloaders for this
                                                                        scenario
                                                                     9. Submit a DownloadTask
                                                                        containing exactly this
                                                                        scenario's downloaders
                                                                        (unchanged mechanism)
                                                                     10. taskCompleted on that
                                                                         DownloadTask == all of
                                                                         this scenario's files
                                                                         are done → invoke
                                                                         Results Analysis once
```

### Design decisions this implies

- **`ScenarioInfo.__init__` MUST become Rana-only and MUST NOT trigger `set_simulation_info_from_threedi()` eagerly.** Callers explicitly invoke resolution when ready (inside `ScenarioResolveTask`), rather than it happening implicitly at construction time.
- **One `ScenarioResolveTask` per scenario**, dispatched the same way `resolve_schematisation()` already dispatches one resolution + `DownloadTask` per schematisation, even within a batch. This is a deliberate simplification over resolving once for a whole batch: it fits the existing per-item dispatch loop in `open_items()` with no restructuring, and needs no cross-scenario bookkeeping. The only cost is one extra `get_threedi_api()` call per scenario in a batch — cheap in the common case (a `QgsSettings` read if the HCC URL is overridden, otherwise one lightweight Rana `frontend-settings` GET), unlike the potentially slow/flaky `fetch_simulation`/`fetch_3di_model` calls that motivated backgrounding this in the first place.
- **Skip the task entirely when unnecessary**: if a scenario is either not 3Di-linked or already has complete metadata from the descriptor alone (the existing early-return check in `set_simulation_info_from_threedi()`), proceed straight to the decision step without spinning up a `QgsTask` for that scenario.
- **Task failures stay scoped to that scenario, not the whole operation.** `set_simulation_info_from_threedi()` already catches `ApiException` and falls back to `has_3di_simulation = False`; the task itself only fails/terminates on cancellation, consistent with decision `20260831-1500`'s "unavailable scenarios are skipped and reported, valid items continue."
- **Cancellation**: `isCanceled()` checked inside the task; if a scenario's resolve task is terminated, no `DownloadTask` is submitted for that scenario, and a warning is shown (same pattern as `handle_download_terminated`). Other scenarios in the same batch are unaffected since each has its own task pair.
- **Per-scenario completion is trivial**: since each scenario's `DownloadTask` contains only that scenario's downloaders (raw zip + attached results), `taskCompleted` on that task directly means "this scenario's files are all done" — the exact same `taskCompleted → on_downloaded` idiom `resolve_schematisation()` already uses. No cross-scenario tracking structure is needed.
- **Progress bar UX**: `set_progress_bar_busy("Resolving scenario details…")` during `ScenarioResolveTask`, handed off to the existing per-file `DownloadTask.file_started` progress once the real download begins — a two-phase busy→progress experience, without a new dialog.
- **Guard against missing/unconfigured 3Di API** the same way `resolve_schematisation()` already does (`get_threedi_api() is None` check, `loader.py:1027-1032`) — degrading that one scenario to raw-results-only with a message-bar warning rather than aborting the whole batch.

### Relationship to schematisation opening (not in scope here)

`resolve_schematisation()` has the same category of problem (`tc.fetch_schematisation_revisions(...)` called synchronously before showing the Replace/Store/Cancel dialog) and is currently accepted as single-item-only blocking behavior. There is already an unused non-interactive variant, `resolve_schematisation_download_dir_auto()` (`simulation/utils.py:776`), intended for batch use but only wired from `legacy/loader.py` today — meaning batch/folder schematisation opens currently show one sequential interactive dialog per schematisation. Retrofitting the same background-resolution approach there is plausible but is a separate, pre-existing gap in already-shipped code, not part of this feature. Noted here as a candidate follow-up, not a task.

## Requirements

### Functional Requirements

- **FR-001**: The current `Loader` MUST provide the scenario-results entry point and MUST use `DownloadTask` rather than legacy `QThread` workers.
- **FR-002**: The individual-scenario flow MUST preserve the `ResultBrowser` choices for attached results, raw results, nodata, pixel size, and CRS.
- **FR-003**: The result-selection dialog MUST be moved from `legacy/widgets` to the current `widgets` package, with no dependency on the legacy loader.
- **FR-004**: Batch and folder operations MUST accept scenario files and MUST use defaults without displaying `ResultBrowser`.
- **FR-005**: Batch defaults MUST download raw `results.zip` and the attached result named `max water depth (file)`; generated raster results MUST NOT be requested in batch mode.
- **FR-006**: Scenarios in a batch selection MUST download via their own `DownloadTask` (one per scenario), consistent with how vector, raster, and schematisation files in the same batch are already dispatched independently today; no new shared-batch-task mechanism is introduced.
- **FR-007**: After successful completion, the loader MUST invoke Results Analysis automatically, once per completed scenario directory, passing the project context so results can be organized by project. This MUST NOT show a confirmation prompt (e.g. "Do you want to add the results…?") — the legacy/current `_add_layer_from_scenario` confirmation dialog is replaced by automatic loading, for both the single-scenario and batch flows.
- **FR-008**: Layer-tree interactions and `RanaLayerRef` MUST remain unchanged in this feature. Scenario linkage MUST remain in loader-level download records/context for future integration.
- **FR-009**: Batch skips, download failures, unavailable Results Analysis, and compatibility warnings MUST be communicated through the message bar.
- **FR-010**: Legacy scenario-result orchestration, dialog imports, and signal wiring MUST be removed or become unused after the current flow is active; legacy download worker classes MUST NOT be copied.
- **FR-011**: UI and Results Analysis layer loading MUST occur through main-thread callbacks after background downloads complete.
- **FR-012**: `ScenarioInfo` construction MUST NOT trigger 3Di API calls eagerly. Any 3Di resolution needed to fill incomplete descriptor metadata (`set_simulation_info_from_threedi()`) MUST run inside a dedicated background `ScenarioResolveTask(QgsTask)`, one per scenario — covering both the single-scenario and batch flows via the same mechanism — before the interactive dialog or batch-default decision is made for that scenario. Resolution MUST fail safely per scenario (fallback to not-linked/raw-results-only, message-bar warning) if the 3Di API is unavailable, unconfigured, or that scenario's lookup fails, rather than blocking the UI, aborting the whole batch, or raising an unhandled exception.

### Key Entities

- **Scenario request**: A project/file pair representing one scenario to open, optionally originating from a context action, multi-selection, or folder expansion.
- **Scenario download record**: Loader-owned context for one scenario containing its metadata, project/file identity, and target results directory — needed to invoke Results Analysis once that scenario's `DownloadTask` completes.
- **Result selection**: Interactive result IDs and generation parameters returned by `ResultBrowser`; batch selections are the fixed defaults above.
- **`ScenarioResolveTask`**: A `QgsTask` that resolves 3Di simulation metadata for one `ScenarioInfo` in the background (see "Threading Considerations"). One instance per scenario being opened.

## API and Component Changes

- `rana_qgis_plugin/loader.py`: add scenario request preparation, `ScenarioResolveTask` submission, interactive/batch result selection, downloader construction, task completion handling, per-scenario completion tracking, and `open_scenario_results` orchestration.
- `rana_qgis_plugin/utils/scenario.py`: `ScenarioInfo.__init__` becomes Rana-only (no eager 3Di call); `set_simulation_info_from_threedi()` remains but is invoked explicitly by `ScenarioResolveTask`, not from the constructor.
- `rana_qgis_plugin/widgets/result_browser.py`: current-package home for the preserved dialog.
- `rana_qgis_plugin/data_items/file_item.py`: connect the scenario's primary open action and double-click path to the current loader.
- `rana_qgis_plugin/data_items/file_actions.py`: expose the scenario primary open action for single and batch open paths; no separate download-results action is used.
- `rana_qgis_plugin/workers/download.py`: reuse existing result contexts/downloaders and `DownloadTask`; only adapt interfaces if required by the current loader.
- `rana_qgis_plugin/layer_management/layer_manager.py`: extract `_add_layer_from_scenario`'s Results Analysis call (and its `project`-argument/old-signature fallback) into the current loader, dropping the existing user-confirmation prompt — Results Analysis loading becomes automatic per decision `20260921-1600-scenario-results-automatic-loading` — without adding layer-panel interactions.

## Testing

- Test the observable `ScenarioInfo` contract: constructing from incomplete Rana metadata remains usable without a reachable 3Di service, while explicit `set_simulation_info_from_threedi()` performs resolution and either fills the missing metadata or safely falls back when the service fails. An implementation-level assertion that construction does not call the 3Di client may supplement this, but is not the primary behavior test.
- Unit-test `ScenarioResolveTask` resolution: success, 3Di failure (falls back to not-linked), missing/unconfigured 3Di API, cancellation.
- Unit-test the "skip the task when no 3Di resolution is needed" short-circuit.
- Unit-test default result selection and scenario skip decisions.
- Unit-test single-scenario and batch downloader construction.
- Test that a batch containing scenario, vector, and raster requests dispatches one `DownloadTask` per item, unaffected by each other.
- Test that a scenario's Results Analysis invocation fires once, after its own `DownloadTask` completes.
- Test Results Analysis missing and old-signature fallback paths.
- Manual UI testing: individual scenario action, multiple selected scenarios, folder containing scenarios, mixed folder, skipped/incomplete scenario, failed download, and a scenario batch during a slow/unreachable 3Di backend (verify UI stays responsive).

## Success Criteria

### Measurable Outcomes

- **SC-001**: An individual scenario can be selected, downloaded, and opened in Results Analysis without invoking legacy loader workers.
- **SC-002**: A batch containing multiple scenarios produces no result-selection dialogs and opens every successfully downloaded scenario exactly once.
- **SC-003**: A mixed batch continues to process valid vector, raster, and scenario items when one scenario is unavailable.
- **SC-004**: No long-running download or result-generation operation blocks the QGIS UI thread, including each scenario's `ScenarioResolveTask` 3Di resolution step ahead of dialog display or batch-default processing — verified with multiple scenarios requiring 3Di resolution in one batch.

## Scope Boundaries

Included: current-loader orchestration, preserved interactive dialog, default batch behavior, multi-select/folder support, automatic Results Analysis loading, message-bar feedback, and background `ScenarioResolveTask` for 3Di metadata resolution.

Not included: layer-panel actions for scenario results, extending `RanaLayerRef`, changing Results Analysis plugin internals, adding a new combined multi-scenario selection dialog, or retrofitting the same background-resolution approach onto schematisation opening (noted as a candidate follow-up).

## Addendum: Scenario-action gating and Results Analysis serialization

**Added**: 2026-09-25

### Problem

`ra_tool.load_result()` is a synchronous, main-thread-only integration point. The
Results Analysis plugin performs QGIS project and layer-tree work there, and its
grid/layer generation can process Qt events while it is running. If multiple
scenario downloads complete close together, a second completion callback can
re-enter the Results Analysis hand-off before the first call returns. A user can
also start another scenario-results action while the previous action is still
downloading or opening results.

The solution is entirely in this plugin. The `threedi-results-analysis` plugin
must not be changed.

### Design

Two separate protections are required:

1. **Scenario-action gate**: only one user-initiated scenario-results action is
   active at a time. A second scenario action is rejected with a warning. This
   applies only to scenario-result opens; unrelated file, layer, and
   schematisation requests in a mixed batch continue normally. The existing
   `open_items` limit of 50 items and confirmation above 10 remains unchanged.
2. **Results Analysis queue**: scenarios within the active action may still
   download concurrently. When each download completes, its Results Analysis
   hand-off is appended to a FIFO queue. The queue drains one item at a time,
   ensuring that `open_scenario_results_in_results_analysis()` is never
   re-entered while a previous call is active.

The action gate remains active until every scenario has either been skipped,
cancelled, failed, or successfully handed off to Results Analysis. Every
existing early return in the scenario pipeline must release exactly one gate
slot. The queue must also release its slot in a `finally`-equivalent path so a
failure in one hand-off cannot leave the action permanently busy or prevent
later queued items from opening.

This does **not** wait for all downloads before opening the first completed
scenario. Downloads and opening continue to overlap: downloads run in the
background, while only the Results Analysis hand-offs are serialized.

### Requirements

- `Loader` MUST track the active scenario action and its pending scenario count.
- A second single or batch scenario-results action MUST be rejected while the
  gate is active, with a clear message-bar warning and no new scenario task.
- A mixed batch MUST continue processing non-scenario requests when its scenario
  requests are rejected by the gate.
- The gate MUST be released for descriptor errors, not-ready scenarios,
  resolution cancellation/failure, dialog cancellation, empty selections,
  batch skips, missing task managers, download cancellation/failure, and
  successful Results Analysis hand-off.
- Results Analysis hand-offs MUST be queued and processed FIFO, one at a time.
- A failed Results Analysis hand-off MUST be reported and MUST NOT prevent later
  queued hand-offs from being processed.
- The per-download message-bar clearing callback MUST be replaced by clearing
  only when the complete scenario action has finished.
- A busy-style progress message MUST be shown while Results Analysis hand-offs
  are being processed.
- No files in `../threedi-results-analysis` may be modified.

### Testing and manual verification

Unit tests MUST cover the gate rejecting a second action, mixed-batch behavior,
all gate-release outcomes, FIFO queue draining, re-entrant completion attempts,
and continued processing after one hand-off fails.

Manual testing MUST proceed in this order:

1. Open one scenario and immediately attempt another single or batch scenario
   open. Verify the second action is rejected and the gate eventually clears.
2. Open a batch of at least three scenarios with staggered completion. Verify
   downloads continue in parallel, Results Analysis opens each completed result
   one at a time, and the UI reports progress without crashes or duplicate
   loads.
3. Run a combined regression check for both behaviors in one QGIS session.
