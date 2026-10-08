---
feature: feat_464_wire_simulation
status: planned
created: 2026-10-01
chunk_size: adaptive
total_tasks: 7
estimated_lines: 215
---

# Tasks: Wire Simulation button in schematisation revision history

**Input**: `.minispec/specs/feat_464_wire_simulation/design.md`
**Branch**: `feat_464_wire_simulation`

## T001: Shared process-link popup helper

- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:** Add `Loader.show_process_link_popup(parent, title, project_slug, links)`
  where `links` is a list of `(label, job_id)` pairs, rendering one
  `<a href>` line per entry via `get_rana_processes_url`. Update
  `create_model` in `version_history_dialog.py` to call this helper instead
  of its inline `QMessageBox.information` block.
- **Depends on:** None
- **Acceptance:** Create Model flow still shows its popup with a working
  track link; no behavior change visible to the user.
- **Evidence:** Manual test — click "Create" on a revision without a model,
  confirm the popup and link still work as before.

## T002: Convert `SimulationRunner` to `QgsTask` and move orchestration to Loader

- **Estimate:** ~25 lines
- **Files:** `rana_qgis_plugin/simulation/workers.py`, `rana_qgis_plugin/simulation/simulation_wizard.py`, `rana_qgis_plugin/loader.py`
- **Description:** Convert `SimulationRunner` from `QRunnable` to `QgsTask`.
  Keep its custom progress/failure/completion signals and all simulation
  business logic unchanged. Initialize a task description, make `run()`
  return `True` on success and `False` after its existing error-reporting
  paths. `SimulationWizard` only prepares and emits/returns its
  `NewSimulation` list; it must not create or submit `SimulationRunner` and
  must not connect runner signals. `Loader` creates/submits the runner through
  `QgsApplication.taskManager()`, retains its lifecycle, and handles progress,
  failure, and completion through Loader-owned receivers. Expose the completed
  simulation list from Loader for the future tracker integration.
- **Depends on:** T003 for the final wizard constructor shape; independent of T001 and T004
- **Acceptance:** The wizard can close after emitting prepared simulations;
  Loader-owned handling continues to report progress/failure/completion after
  the wizard is gone, and completed simulations are available from Loader.
- **Evidence:** Existing shutdown tests remain unchanged; manual wizard
  testing confirms single- and multiple-simulation creation still reports
  progress and emits completion/failure.

## T003: Add temporary breach layers directly [P]

- **Estimate:** ~15 lines
- **Files:** `rana_qgis_plugin/simulation/simulation_wizard.py`
- **Description:** Remove the obsolete `layer_manager` and `layer_parents`
  constructor parameters. Add valid breach/flowline layers directly to the
  current project through a small `layer_management.layer_manager` module
  helper; these are temporary wizard input layers and are removed by the
  existing `unload_breach_layers()` cleanup. Do not create Rana groups or
  add a class-based compatibility adapter.
- **Depends on:** None (independent of T001/T002)
- **Acceptance:** `SimulationWizard` no longer references `layer_manager` or
  `layer_parents`; breach layers load temporarily and are removed when the
  wizard finishes or is cancelled.
- **Evidence:** Manual test — enable breach events, confirm both temporary
  layers appear for selection and disappear after finish/cancel.

## T004: Pre-flight checks + template data helper

- **Estimate:** ~55 lines (incl. tests)
- **Files:** `rana_qgis_plugin/loader.py`, `tests/loader/test_simulation.py` (new)
- **Description:**
  - Port `get_simulation_data_from_template(tc, template)` from legacy
    `Loader` (fetches simulation/settings/events/lizard overview for a
    template; same `ApiException` handling via `extract_error_message`).
  - Add the pre-flight portion of `start_simulation`: check
    `hcc_working_dir()`, `get_threedi_organisations()` +
    `fetch_organisations(...)`, and
    `fetch_schematisation_revision_3di_models(...)` for an enabled+valid
    model. Each failure path calls `show_warn`/`show_error` and returns
    early (no dialogs opened yet — the dialog chain itself lands in T005).
  - Add unit tests (following the `test_save_revision_requires_authenticated_api`
    pattern: `MagicMock` communication, `patch` the module-level API
    functions) for each pre-flight failure: no working dir, no
    organisations, no enabled/valid model.
- **Depends on:** None
- **Acceptance:** Each pre-flight failure shows the right message and
  returns without opening a dialog.
- **Evidence:** New unit tests pass: `pytest tests/loader/test_simulation.py -q`.

## T005: `Loader.start_simulation` dialog chain

- **Estimate:** ~55 lines
- **Files:** `rana_qgis_plugin/loader.py`
- **Description:** Using the pre-flight result and template helper from
  T004, open `ModelSelectionDialog` → `get_simulation_data_from_template` →
  `SimulationInit` → `SimulationWizard` (using the QGIS task manager for
  `SimulationRunner`, dropping `layer_manager` per T003). Build `layer_parents` from
  `project["name"]`, `file_item["id"]`'s path parts, `schematisation_name`,
  and the revision number (all from the `file_item`/`row_metadata` args —
  see the T007 signature fix). Return silently on any dialog rejection.
   Connect the Loader completion path to
   `start_simulation_tracker_process` in the future tracker integration
    (passing through `project` and `file_item`, see T006). Do not connect the
    runner to the wizard.
- **UI flow:** Close the revision-history dialog before opening the modal
  wizard so breach map tools can interact with the QGIS canvas. Do not reopen
  the history dialog afterward; retain project/file context in Loader for the
  later tracker-process popup.
- **Depends on:** T002, T003, T004
- **Acceptance:** Full manual run from the history dialog button through
  to a created 3Di simulation works; cancelling at any dialog stage exits
  cleanly with no process started and no error shown.
- **Evidence:** Manual test — walk the full happy path once, and cancel at
  each of the 3 dialog stages once each.

## T006: `Loader.start_simulation_tracker_process`

- **Estimate:** ~35 lines (incl. tests)
- **Files:** `rana_qgis_plugin/loader.py`, `tests/loader/test_simulation.py`
- **Description:** For each simulation in the `simulations_initialized` list,
  call `start_tenant_process` with the `simulation_tracker` tag (mirroring
  `start_model_tracker_process`). Collect `(label, job_id)` for successes;
  on a per-simulation `RanaPostError`, `communication.log_err` and continue.
  Call `show_process_link_popup` (T001) with whatever succeeded. Add a unit
  test for the partial-failure case (2 simulations, one `start_tenant_process`
  raises) confirming the popup only lists the surviving one and the error
  is logged.
- **Depends on:** T001
- **Acceptance:** Partial failure doesn't block remaining simulations or
  crash the popup.
- **Evidence:** `pytest tests/loader/test_simulation.py -q` passes,
  including the partial-failure case.

## T007: Wire the Simulation button

- **Estimate:** ~20 lines
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:** Remove `show_simulation_placeholder`. In
  `render_action_widget`, connect the column-4 button to a new
  `start_simulation(row, button)` method that disables the button, calls
  `self.loader.start_simulation(self.project, self.file_item, row.metadata, self)`
  (fixing `Loader.start_simulation`'s signature to accept `file_item`,
  needed for `layer_parents` and the tracker process's output path — see
  design.md API/Interface), and re-enables the button in a `finally` block.
- **Depends on:** T005, T006; T005 depends on the revised T002/T003 task-ownership boundary
- **Acceptance:** Clicking "Simulation" on a modeled revision launches the
  wizard chain end-to-end and the button is clickable again afterward
  regardless of outcome.
- **Evidence:** Manual test — full regression pass (see Manual Test Plan
  below).

---

## Manual Test Plan (run once T001–T007 are all complete)

1. Open a schematisation's revision history, pick a revision with a model.
2. Click **Simulation**; confirm the button disables immediately and the
   Model Selection dialog opens without a long wait.
3. Pick a template, proceed through Simulation Init, run the full wizard,
   finish it. Confirm a popup appears with a working track link, and the
   button is enabled again.
4. Repeat but cancel at Model Selection — confirm silent return, button
   re-enabled, no process started.
5. Repeat but cancel at Simulation Init — same check.
6. Repeat but cancel inside the full wizard — same check.
7. Enable "multiple simulations" in Simulation Init and run 2+ simulations
   in one go — confirm the popup lists a track link per simulation.
8. Temporarily misconfigure (e.g. clear the working directory setting) and
   click Simulation — confirm a modal warning, no dialog opens, button
   re-enabled.
9. Re-run the existing Create Model flow once, to confirm the T001 popup
   refactor didn't change its behavior.

## Notes

- No new files are introduced; every task edits existing modules, per the
  constitution's conservative abstraction threshold.
- Tests are added where they're cheap and valuable (pre-flight branches,
  partial-failure handling in T004/T006) and skipped where they'd require
  heavy Qt dialog mocking (T003, T005, T007) — those rely on the manual
  test plan instead, per the testing philosophy in AGENTS.md.
- T003 can be done in parallel with T001/T002/T004 since it only touches
  `simulation_wizard.py`.

## Progress
- [x] T001: Shared process-link popup helper
- [x] T002: Convert `SimulationRunner` to `QgsTask` and move orchestration to Loader
- [x] T003: Add temporary breach layers directly [P]
- [ ] T004: Pre-flight checks + template data helper
- [ ] T005: `Loader.start_simulation` dialog chain
- [ ] T006: `Loader.start_simulation_tracker_process`
- [ ] T007: Wire the Simulation button
