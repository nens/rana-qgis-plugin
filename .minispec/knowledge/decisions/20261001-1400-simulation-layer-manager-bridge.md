# Decision: Bridge SimulationWizard's layer_manager calls directly

**ID:** 20261001-1400-simulation-layer-manager-bridge
**Date:** 2026-10-01
**Status:** Accepted

## Context

`SimulationWizard` (already ported to `rana_qgis_plugin/simulation/`) calls
`self.layer_manager.add_layer(layer, parents)` in exactly 2 places (breach
layer loading). This was `legacy.layer_manager.FileLayerManager`, a class
which no longer exists in the repo. The current codebase uses a
module-of-functions design in `rana_qgis_plugin/layer_management/layer_manager.py`
(`find_or_create_rana_groups`, `add_layer_to_group`, etc.) instead of a class.

## Decision

Edit the 2 call sites in `simulation_wizard.py` directly to call
`find_or_create_rana_groups(layer_parents)` + `add_layer_to_group(layer, group)`.
Drop the `layer_manager` constructor parameter from `SimulationWizard`
entirely.

## Reasoning

- Only 2 call sites — introducing an adapter class to preserve a
  `.add_layer(layer, parents)` interface would add an abstraction for no
  future benefit.
- Matches repo convention (AGENTS.md: prefer module-of-functions, don't
  copy legacy class patterns blindly).

## Consequences

`SimulationWizard`'s constructor signature changes (one fewer parameter),
so `Loader.start_simulation` constructs it without a `layer_manager` arg.
