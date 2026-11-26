---
type: decision
id: 20261125-1000-sim-result-destination-separate-from-name
date: 2026-11-25
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/simulation/simulation_wizard.py
  - rana_qgis_plugin/loader.py
tags: [simulation, wizard, results, destination]
participants: [margriet, agent]
---

# Simulation result destination is separate from the simulation name

## Context

The Rana location of simulation results is not decided by 3Di. After 3Di
creates the simulation, `Loader.start_simulation_tracker_process` starts a Rana
`simulation_tracker` process. The plugin passes the results path as
`outputs.results.id`:
`{schematisation_folder}{simulation_name}_{sim_id}_results.zip`.
Typing `results/foo` as the name works only because the name is copied into
that path. As a side effect, the 3Di simulation is named `results/foo`.

## Options Considered

- **Separate destination value** (chosen): the wizard returns a destination
  folder next to the prepared simulations. The loader inserts it into
  `outputs.results.id`. Nothing is sent to 3Di.
- Prefix in the name: a selector writes `folder/` into the name field. This
  needs almost no plumbing, but the 3Di name contains the path, and the batch
  suffix (`_1`, `_2`) and template-loaded names get mixed up with the folder.

## Decision

The destination folder is its own value and is used only to build the Rana
tracker output path. The 3Di simulation name stays as the user typed it. The
3Di API is not changed.

## Consequences

- The destination has to travel from the wizard to
  `start_simulation_tracker_process`. It does so on `NewSimulation` (see
  `20261125-1040-results-folder-on-new-simulation`), so the signal wiring is
  unchanged.
- If the user leaves the destination empty, the current behaviour is unchanged
  (results go next to the schematisation file).
