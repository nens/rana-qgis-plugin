---
type: decision
id: 20261029-1108-processes-simulation-cancel
date: 2026-10-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/processes_panel.py
  - rana_qgis_plugin/simulation/threedi_calls.py
tags: [processes, simulation, cancellation]
participants: [engineer, assistant]
---

# Processes cancellation is limited to simulation jobs

## Context

The engineer chose to include cancellation with the initial window. Legacy's `cancel_simulation` path extracts `job.inputs["simulation_id"]` and invokes a 3Di simulation shutdown action through `ThreediCalls`; it is not a generic Rana jobs cancellation endpoint. The legacy row button is shown for every running job, without guarding for a simulation ID.

Legacy's actual eligibility check (`ProcessesBrowser.add_item`/`.update_state_for_job`, lines 217 and 287) is not "has `inputs.simulation_id`" — it resolves the simulation-tracker process id once via `get_process_id_for_tag("simulation_tracker")` (already current, non-legacy: `utils/api.py:808`) and compares `job.process_id == simulation_tracker_process_id`. `inputs["simulation_id"]` is only read afterward, as the 3Di action's payload. The process-id comparison is the more precise, already-proven check and should be reused instead of a presence-check heuristic.

Legacy's `cancelled_sim_map` + `on_simulation_cancel_requested`/`on_simulation_cancelled` bookkeeping (lines 110, 237-249) exists only because legacy's cancel is asynchronous: it emits a `cancel_simulation` signal and waits for a later `on_simulation_cancelled` slot call once `Loader`'s 3Di call succeeds elsewhere. This repo's cancel call is synchronous (decided below), so there is no "wait for a later confirmation" gap to bridge, and this bookkeeping has no equivalent need here.

Legacy's handler (`legacy/loader.py:Loader.cancel_simulation`, lines 2017-2032) also calls `tc.fetch_simulation_status(simulation_pk)` before the shutdown action, but never uses its return value — this looks like dead/vestigial code and is not ported.

Whether to run the cancel call synchronously or via a one-shot `QgsTask` (like the jobs poll) was raised and discussed explicitly, since this decision had previously asserted "synchronous" without surfacing it as its own choice. Resolved in favor of synchronous: this is a short, single, explicit action already gated by a confirmation dialog — not a recurring background operation. A `QgsTask` would also need to decide whether it exposes `CanCancel`, and letting a user cancel an in-flight cancel-simulation request is itself confusing; not setting `CanCancel` avoids that but still adds task-lifecycle overhead (registration, completion-after-dock-closed handling) disproportionate to a bounded, rare, already-confirmed click.

## Options Considered

### Option 1: Omit cancellation

Ship only monitoring and details.
- ✅ Smallest initial implementation.
- ❌ The engineer explicitly wants cancellation included in this feature.

### Option 2: Generic job cancellation

Offer cancel for all running jobs.
- ❌ No generic cancellation API has been established; the legacy operation is simulation-specific.

### Option 3: Simulation-only cancellation

Offer cancel for running jobs whose `process_id` matches the resolved simulation-tracker process.
- ✅ Reuses the existing 3Di shutdown action and legacy's own (already-proven) eligibility check.
- ✅ Avoids legacy's missing-key failure on non-simulation jobs.
- ❌ Only simulation jobs are cancellable in this feature.

## Decision

Include cancellation in the same implementation slice as the Processes window. `job_can_be_cancelled(job: JobData, simulation_tracker_process_id: str | None) -> bool` lives in `widgets/jobs_models.py` alongside `JobData`, checking `job.status == "running" and job.process_id == simulation_tracker_process_id` — not `inputs.simulation_id` presence, matching legacy's actual check. `simulation_tracker_process_id` is resolved once (e.g. on panel open) via the existing `get_process_id_for_tag("simulation_tracker")`.

On cancel: ask for confirmation, disable the cancel affordance the moment the action starts, then call `ThreediCalls.create_simulation_action(job.inputs["simulation_id"], name="shutdown")` synchronously — no `cancelled_sim_map`/signal round-trip needed, since the call itself is synchronous. `tc.fetch_simulation_status(...)` is not ported (unused return value in legacy).

Button state is a transition, not a disable/re-enable pair:
- **On success**: do not "re-enable" the button — update the job's status to `"cancelling"` in the model immediately. Since `job_can_be_cancelled` already requires `status == "running"`, the affordance naturally disappears/disables once status changes, avoiding a confusing moment where a freshly-clicked cancel button appears active again.
- **On failure**: re-enable the button and show the error — the job is still actually running and remains actionable.

A later jobs poll is authoritative for the final state either way.

## Consequences

### Positive
- ✅ Delivers the cancellation behavior requested by the engineer.
- ✅ Reuses legacy's actual (process-id-based) eligibility check instead of a weaker presence heuristic.
- ✅ Avoids legacy's missing-key failure on non-simulation jobs.
- ✅ Uses the existing 3Di API wrapper rather than inventing generic job cancellation.
- ✅ Drops legacy's `cancelled_sim_map`/signal round-trip entirely, since the synchronous call makes it unnecessary.

### Negative
- ⚠️ The synchronous shutdown request must be sufficiently short; report API errors and revisit threading if it can block for a noticeable duration.
- ⚠️ Other job types remain view-only until a supported generic cancellation endpoint is designed.

## Code References

- Legacy eligibility check and signal use: `rana_qgis_plugin/legacy/widgets/processes_browser.py:ProcessesBrowser` (process-id comparison: lines 217, 287; `cancelled_sim_map` bookkeeping: lines 110, 237-249)
- Legacy 3Di shutdown handler: `rana_qgis_plugin/legacy/loader.py:Loader.cancel_simulation`
- Current 3Di wrapper: `rana_qgis_plugin/simulation/threedi_calls.py:ThreediCalls`
- Current process-id lookup (already non-legacy): `rana_qgis_plugin/utils/api.py:get_process_id_for_tag`

## Related Decisions

- `20261029-1107-processes-table-filters-details`

## Notes

Manual testing should verify both a running simulation job with `simulation_id` and a running job without it. Do not modify the legacy implementation.
