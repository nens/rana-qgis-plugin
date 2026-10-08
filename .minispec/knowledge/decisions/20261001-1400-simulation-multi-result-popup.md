# Decision: One tracker process + one popup link per created simulation

**ID:** 20261001-1400-simulation-multi-result-popup
**Date:** 2026-10-01
**Status:** Accepted

## Context

`SimulationWizard.simulation_created` emits a list, since the wizard's
"multiple simulations" option can create more than one 3Di simulation in a
single run. Legacy started one `simulation_tracker` Rana process per
simulation in the list.

## Decision

Keep that behavior: start one `simulation_tracker` process per simulation,
and show a single popup listing one track-link per simulation that
successfully started a process. If starting a tracker process fails for one
simulation, log it and continue with the rest; omit it from the popup.

## Reasoning

- The multi-simulation wizard feature already exists and is exercised by
  users; silently only handling the single-simulation case would regress
  existing functionality.
- Partial failure (one of several `start_tenant_process` calls failing)
  shouldn't block the others from being tracked.

## Consequences

`show_process_link_popup` is designed to take a list of (label, job_id)
pairs from the start, rather than a single link, avoiding a later signature
change.
