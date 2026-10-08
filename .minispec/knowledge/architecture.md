# Architecture

## Rana browser and schematisation integration

Rana resources are exposed through QGIS data items. Opening resources flows
through a loader and QGIS task, then delegates layer creation to
`LayerManager`. Schematisations use the same orchestration but resolve revision
metadata and local working paths before downloading.

Scenario result opens use the same current-loader and `QgsTask` path. Individual
opens use the result-selection dialog; multi-select and folder operations use
default raw and attached-result downloads. Completion groups files by scenario
and invokes Results Analysis once per scenario.

Loaded resources are identified in the layer tree through custom properties on
their groups/layers. Layer-tree actions are registered centrally by
`LayerTreeMenuProvider`. Long-running downloads and uploads use `QgsTask`; Qt UI
and layer-tree mutations remain on the main thread.

## File and revision history

File Browser history is exposed through the `FileAction.VERSION_HISTORY`
context-menu action. Generic files, folders, and the Files root use the Rana
project file-history endpoint. Schematisation files use the 3Di revision API.
Both sources are rendered by dialogs in
`rana_qgis_plugin/widgets/version_history_dialog.py`, structured as an
abstract `HistoryDialog` base (table, model, Refresh, error/empty-state
labels, fetch/refresh lifecycle) with two sibling subclasses:
`RanaHistoryDialog` for generic history and
`SchematisationRevisionHistoryDialog` for revisions. Neither subclass
inherits from the other; each only implements how its table is fetched and
built. The schematisation subclass preserves `Simulation` and `Rana Model`
row-action columns whose buttons follow the legacy enablement rules.
`Rana Model` (create/delete) and `Simulation` both delegate to `Loader`
methods (`start_model_tracker_process`/`delete_schematisation_revision_3di_model`
and `start_simulation`/`start_simulation_tracker_process` respectively).
`Simulation` opens the existing (already-ported, non-legacy)
`ModelSelectionDialog` → `SimulationInit` → `SimulationWizard` chain from
`rana_qgis_plugin/simulation/`, reusing the row's already-fetched revision
metadata rather than re-fetching it, then starts one Rana `simulation_tracker`
process per created 3Di simulation. Both action columns report their Rana
process link(s) through a shared `Loader.show_process_link_popup` helper.
Both subclasses
fetch their complete data set eagerly on open — `RanaHistoryDialog`
aggregates all cursor pages internally (mirroring `get_tenant_project_files()`),
and `SchematisationRevisionHistoryDialog` fetches all revisions — so neither
has a `Load more` control.

The initial revision-history version fetches all revisions synchronously
through `fetch_schematisation_revisions()` so it can calculate exact legacy
`Simulation` and `Rana Model` button enablement from the complete model count.
The method's existing behavior remains unchanged for simulation and upload
flows. Async fetching or an aggregate count endpoint is a later,
latency/API-driven optimization for either history source.

The legacy `RevisionsView` remains reference-only. Its table fields and action
column shape inform the native dialog, but its widget, legacy browser wiring,
legacy action enum, auth helper, communication object, and loader signals are
not moved into the native architecture. Current API/client and native Qt
patterns are reused instead.
