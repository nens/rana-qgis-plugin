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

- **Required field on `NewSimulation`** (chosen): `results_folder: str`, set
  by the wizard to the schematisation folder unless the user chose another.
- Separate argument passed through `start_simulations`, the
  `initializing_simulations_finished` lambda and the tracker: keeps the data
  model free of Rana fields, but needs changes in three signatures.

## Decision

- `NewSimulation.results_folder` always holds a Rana project path with a
  trailing slash (e.g. `models/river/results/`). There is no `None` default.
- `SimulationWizard.results_folder` holds the chosen folder. It is initialized
  from the `schematisation_folder` argument on init, and the picker (Task 3/4)
  will modify it. The wizard copies it to every simulation it creates (batch
  runs included).
- The tracker uses `simulation.results_folder` only. The file name stays
  `{name}_{id}_results.zip`.
- `SimulationWizard` gets a new constructor argument `schematisation_folder`
  (trailing slash), passed from `Loader.start_simulation`. The picker will
  additionally need `project` (dict, for the root label) in Task 4.

## Consequences

- The data model gets one Rana-specific field (there is already a precedent:
  `started_from`).
- One source of truth: the tracker no longer decides a default.
- No changes to `start_simulations` or the signal wiring.
