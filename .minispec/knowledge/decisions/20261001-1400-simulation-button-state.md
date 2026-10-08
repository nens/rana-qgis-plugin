# Decision: Simulation button disables only during the flow, always re-enables

**ID:** 20261001-1400-simulation-button-state
**Date:** 2026-10-01
**Status:** Accepted

## Context

The "Rana Model" (Create) button in the same dialog disables permanently
after a successful click, until the user hits Refresh — appropriate because
a revision can only have one model (`threedimodel_limit`-gated). The
Simulation button has no such limit: a single modeled revision can be used
to start many simulations.

## Decision

Disable the Simulation button only for the duration of
`Loader.start_simulation()` (dialog chain + tracker-process calls), and
re-enable it in a `finally` block regardless of outcome (success, any
dialog cancellation, or pre-flight error).

## Reasoning

- Prevents double-invocation from a rapid double-click while dialogs are
  being constructed.
- Matches the actual domain constraint (no limit on simulations per model)
  rather than copying Create Model's permanent-lock pattern, which doesn't
  apply here.

## Consequences

No "click Refresh to check status" messaging needed for Simulation, unlike
Create Model.
