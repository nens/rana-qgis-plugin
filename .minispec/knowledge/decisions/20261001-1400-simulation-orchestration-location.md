# Decision: Orchestration lives in Loader, not a new module

**ID:** 20261001-1400-simulation-orchestration-location
**Date:** 2026-10-01
**Status:** Accepted

## Context

Starting a simulation requires a sequence of modal dialogs
(`ModelSelectionDialog` → `SimulationInit` → `SimulationWizard`) followed by
starting Rana tracker process(es). This needs to live somewhere that owns
both the dialog sequencing and the final `start_tenant_process` calls.

## Decision

Add `Loader.start_simulation()` and `Loader.start_simulation_tracker_process()`
methods. No new dedicated module/class.

## Reasoning

- `Loader.save_revision()` already owns an equivalent modal dialog chain
  (`UploadWizard`) followed by background task kickoff, so this is a
  consistent, existing pattern in the codebase.
- A separate module would only add indirection for a single call path with
  no reuse elsewhere.

## Consequences

`loader.py` grows by two methods and one small shared popup helper; no new
files needed for the orchestration itself.
