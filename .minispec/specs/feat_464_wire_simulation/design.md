---
feature: wire-simulation-button
status: complete
created: 2026-10-01
decisions:
  - 20261001-1400-simulation-layer-manager-bridge
  - 20261001-1400-simulation-data-reuse
  - 20261001-1400-simulation-orchestration-location
  - 20261001-1400-simulation-multi-result-popup
  - 20261001-1400-simulation-button-state
  - 20261001-1400-simulation-preflight-errors
  - 20261001-1400-simulation-popup-helper-dedup
---

# Wire Simulation Button Design

## Overview

`SchematisationRevisionHistoryDialog` shows a "Simulation" action button per
revision (enabled only when the revision has a Rana/3Di model), but it is
currently wired to `show_simulation_placeholder()`, a no-op message box. This
feature wires that button to the already-ported 3Di simulation wizard chain
(`ModelSelectionDialog` → `SimulationInit` → `SimulationWizard`, all living in
`rana_qgis_plugin/simulation/`), reusing revision data already fetched for the
history table, and finishes by starting one Rana `simulation_tracker` process
per created 3Di simulation — mirroring the existing "Create Model" flow,
including a popup with link(s) to track progress in Rana.

Because breach configuration can activate QGIS map tools, the history dialog
is closed before the modal simulation wizard is shown. The history dialog is
not reopened afterward. Loader owns the asynchronous simulation task and the
eventual Rana process-link popup because the history dialog no longer exists
when task completion arrives.

Investigation confirmed the wizard UI itself is **not legacy** — it was
already ported and works standalone. `legacy/loader.py` (the reference for
the old orchestration, `Loader.start_simulation`) is itself currently broken
(imports modules removed during porting), confirming it is reference-only per
repo convention. The only missing piece is the orchestration glue and the
final process-start/popup step.

## User Stories

- As a schematisation owner, I want to click "Simulation" on a revision with
  a model so that I can configure and launch a 3Di simulation without
  leaving QGIS.
- As a user, I want the simulation configuration dialogs to open promptly
  after clicking, without a long blocking wait for redundant network calls.
- As a user, I want a popup with a link to track my simulation's progress in
  Rana after I finish the wizard, consistent with the Create Model flow.
- As a user, I want to be able to start multiple simulations for the same
  revision over time (unlike model creation, which is limited).

## Components

### `rana_qgis_plugin/loader.py` (`Loader`)

- `SimulationRunner` is converted from `QRunnable` to `QgsTask`, so QGIS's
  existing task manager owns its execution. `Loader` creates and submits the
  runner through `QgsApplication.taskManager()`, retains the active task until
  completion/termination, and owns the durable signal receiver. The wizard is
  never connected to runner signals and does not submit background work.
- Loader exposes the initialization completion path with the initialized
  simulations so a future `simulation_tracker` integration can be attached
  without keeping the wizard alive.
- `start_simulation(self, project: dict, row_metadata: dict, parent) -> None`
  — new method, the orchestration entry point called directly from the
  history dialog's button handler. Owns the synchronous modal dialog chain,
  mirroring how `save_revision()` already owns the `UploadWizard` chain.
- `start_simulation_tracker_process(self, project: dict, file_item: dict, simulations: list) -> None`
  — new method. For each simulation in `simulations` (the list emitted by
  Loader after `SimulationRunner` completes), calls `start_tenant_process` with
  the `simulation_tracker` process tag (same pattern as
  `start_model_tracker_process`), then shows a popup with one track-link per
  started simulation.
- `show_process_link_popup(parent, title: str, project_slug: str, links: list[tuple[str, str]]) -> None`
  — new small shared helper (label, job_id pairs → rendered as one or more
  `<a href>` lines in a `QMessageBox.information`). Replaces the
  ad-hoc `QMessageBox` + `get_rana_processes_url` block currently inlined in
  `create_model`; `create_model` is updated to call this helper too.

### `rana_qgis_plugin/widgets/version_history_dialog.py` (`SchematisationRevisionHistoryDialog`)

- `show_simulation_placeholder` is removed. The column-4 button's
  `clicked` connection (in `render_action_widget`) is changed to call a new
  `start_simulation(row, button)` method:
  - Disables the button for the duration of the call.
  - Calls `self.loader.start_simulation(self.project, row.metadata, self)`.
  - Re-enables the button in a `finally` block regardless of outcome
    (success, cancel at any dialog stage, or pre-flight/runtime error) —
    unlike `create_model`, which disables permanently until Refresh, because
    a modeled revision can run many simulations.

### `rana_qgis_plugin/simulation/simulation_wizard.py` (`SimulationWizard`)

- The wizard only collects the configured `NewSimulation` objects and emits
  them through `simulations_prepared` before accepting. It does not create or
  submit `SimulationRunner` and does not receive runner progress, failure, or
  completion signals.
- Drop the `layer_manager` and `layer_parents` constructor parameters and
  the 2 legacy `self.layer_manager.add_layer(layer, parents)` calls for
  breach layers. These layers are temporary wizard inputs, not Rana-managed
  layers: add valid breach/flowline layers directly with
  `layer_management.layer_manager.add_layer_to_project(layer)`, and let the
  existing `unload_breach_layers()` remove them on finish or cancel. No
  grouping or class-based layer-manager adapter is needed.

## Data Model

No new persisted entities. Reuses:

- `HistoryRow.metadata` from `SchematisationRevisionHistoryDialog.fetch_page()`
  — already contains `revision` (full HCC revision object), `revision_id`,
  `schematisation_id`, `schematisation_name`, `management_url`, `has_model`.
  `Loader.start_simulation` reuses these directly instead of re-fetching
  schematisation/revision data (as legacy's `Loader.start_simulation` did
  redundantly).
- `ThreediCalls` (existing) for the 2 calls that cannot be avoided before
  `ModelSelectionDialog` can open:
  - `get_threedi_organisations()` (existing, no-arg, already used elsewhere)
  - `fetch_schematisation_revision_3di_models(schematisation_id, revision_id)`
    to find the active model (first non-disabled, valid model — same
    selection rule as legacy).

## API / Interface

```python
# Loader
def start_simulation(
    self, project: dict, file_item: dict, row_metadata: dict, parent
) -> None:
    """Open the simulation wizard chain for one schematisation revision.

    `file_item` is the schematisation file dict already held by the history
    dialog (`self.file_item`) — needed to build `layer_parents` for breach
    layers and as the `file_item` passed through to
    `start_simulation_tracker_process` for the tracker process's output path.

    Pre-flight (synchronous, no dialog yet):
      1. hcc_working_dir() must be configured.
      2. get_threedi_organisations() + ThreediCalls.fetch_organisations(...)
         must return at least one organisation.
      3. ThreediCalls.fetch_schematisation_revision_3di_models(...) must
         return an enabled (`not disabled`) and valid (`is_valid`) model.
      Any failure here: self.communication.show_warn / show_error (modal),
      then return — no dialogs opened.

    Dialog chain (all modal, GUI thread):
      1. ModelSelectionDialog(communication, model.id, threedi_api,
         organisations, schematisation_id, parent)
         -> Rejected: return (silent, no error).
      2. get_simulation_data_from_template(tc, selected_template)
         (same helper logic as legacy, ported as a module function)
      3. SimulationInit(current_model, simulation_template,
         settings_overview, events, lizard_post_processing_overview,
         organisation, api=tc, parent=parent)
         -> Rejected: return (silent).
       4. SimulationWizard(hcc_working_dir(), simulation_template,
           organisation, current_model, threedi_api,
           self.communication, layer_parents, simulation_init_wizard, parent)
           connect simulations_prepared to Loader-owned task submission;
          runner progress/failure/completion remains connected to Loader, not
          the wizard. Completion exposes the initialized simulations for the
          future `simulation_tracker` integration.
          -> exec(); Rejected: return (silent, no process started).
    """

def start_simulation_tracker_process(
    self, project: dict, file_item: dict, simulations: list
) -> None:
    """Start one Rana simulation_tracker process per created simulation,
    then show one popup with a track-link per simulation."""

def show_process_link_popup(
    self, parent, title: str, project_slug: str, links: list[tuple[str, str]]
) -> None:
    """Show a QMessageBox with one '<a href>' track-link line per (label, job_id)."""
```

```python
# SchematisationRevisionHistoryDialog
def start_simulation(self, row: HistoryRow, button: QPushButton) -> None:
    """Disable the button, delegate to Loader.start_simulation
    (passing self.project, self.file_item, row.metadata, self), re-enable."""
```

## Edge Cases

- **No working directory configured**: `show_warn`, no dialog, button
  re-enabled.
- **No 3Di organisations available**: `show_warn`, no dialog, button
  re-enabled.
- **No enabled+valid 3Di model for the revision** (shouldn't normally happen
  since the button is only enabled when `has_model` is true, but the model
  could have been disabled/invalidated server-side since the row was
  fetched): `show_warn`, no dialog, button re-enabled.
- **User cancels `ModelSelectionDialog` / `SimulationInit` / `SimulationWizard`**:
  silently return, button re-enabled, no error shown — consistent with
  legacy behavior.
- **`SimulationRunner` fails to initialize simulations**: handled by the
  Loader-owned receiver (`bar_error` plus a Loader failure signal), so the
  wizard may close before the task finishes and no tracker process is started.
- **Multiple simulations from one wizard run** (`simulations_initialized` with
  >1 item, from the wizard's "multiple simulations" option): one
  `simulation_tracker` Rana process is started per simulation; the popup
  lists one track-link per simulation.
- **`start_tenant_process` fails for one of several simulations**: log the
  error (`communication.log_err`) and continue starting the remaining
  ones; the popup only lists links for simulations that successfully
  started a tracker process.

## Open Questions

- None blocking. Known limitation carried over from Create Model: no
  polling or persisted state for in-flight simulations after the popup is
  shown (same limitation documented in `doc/file_history.md` for model
  creation).

## Out of Scope

- Background prefetching of organisations while the history dialog loads.
- Any behavior changes to `ModelSelectionDialog`, `SimulationInit`, or the
  wizard pages themselves beyond the `layer_manager` bridge.
- Polling/persisted tracking of in-flight simulations across dialog
  close/reopen or QGIS restart.

## Implementation status

- The implementation in rana_qgis_plugin/loader.py and supporting modules
  implements the orchestration, task submission via QgsTask, and the
  simulation-tracker process startup. The design is therefore marked
  complete.
- Intentional decisions preserved: the history dialog remains open while
  the modal simulation dialogs are shown (the action button is disabled
  during the call), and the small Create Model single-link popup was kept
  as a dialog-local helper rather than extracting a tiny shared Loader
  helper.
- Manual UI validation of the full flow (history dialog → ModelSelection →
  SimulationInit → SimulationWizard → tracker popup, and cancellation
  paths) remains to be performed before merging to main.
