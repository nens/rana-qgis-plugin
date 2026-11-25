---
type: decision
id: 20261125-1040-results-folder-on-new-simulation
date: 2026-11-25
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/simulation/data_models/simulation_data_models.py
  - rana_qgis_plugin/simulation/simulation_wizard.py
  - rana_qgis_plugin/loader.py
tags: [simulation, results, destination, data-model]
participants: [margriet, agent]
---

# Results folder travels on NewSimulation

## Context

The wizard builds `dm.NewSimulation` objects. After 3Di initialization, the same
objects arrive in `Loader.start_simulation_tracker_process`, which builds
`outputs.results.id`.

## Options Considered

- **Field on `NewSimulation`** (chosen): `results_folder: str | None = None`.
- Separate argument passed through `start_simulations`, the
  `initializing_simulations_finished` lambda and the tracker: keeps the data
  model free of Rana fields, but needs changes in three signatures.

## Decision

- `NewSimulation.results_folder` holds the resolved project path, with a
  trailing slash (e.g. `models/river/results/`), or `None`.
- The wizard sets it on every simulation it creates (batch runs included).
- The tracker uses `simulation.results_folder`, or the schematisation folder
  when it is `None`. The file name stays `{name}_{id}_results.zip`.
- `SimulationWizard` gets two new constructor arguments, `project` (dict; the
  folder picker needs the project name for the root label) and
  `schematisation_folder`, passed from `Loader.start_simulation`.

## Consequences

- The data model gets one Rana-specific field (there is already a precedent:
  `started_from`).
- No changes to `start_simulations` or the signal wiring.
