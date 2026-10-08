# Tasks: Scenario-action gating and Results Analysis serialization

**Input**: `.minispec/specs/feat_455_open_results/design.md` (addendum)
**Branch**: `feat_455_open_results`

## T001: Foundational state and primitives ✅

Add gate and queue state to `Loader.__init__` and implement the helpers for
starting/releasing a scenario action, enqueueing a Results Analysis hand-off,
and draining the queue safely.

## T002: Gate scenario actions while one is busy ✅

Wire the gate into `open_scenario_results` and `open_items`. Add release calls
to all existing scenario-pipeline early returns, including descriptor errors,
resolution cancellation/failure, dialog cancellation, batch skips, missing
task managers, download cancellation/failure, and successful completion.
Add unit tests for second-action rejection, mixed batches, and every release
outcome.

**Manual test first**: open one scenario and immediately attempt another single
or batch scenario open. Verify the second scenario action is rejected, while
unrelated mixed-batch items continue normally, and the gate becomes available
again after the first action finishes.

## T003: Serialize Results Analysis hand-offs ✅

Replace the direct Results Analysis call in
`submit_scenario_result_download` with the FIFO queue, remove per-download
message-bar clearing, add busy-style progress feedback, and ensure queued
entries release the action slot even when one hand-off fails. Add unit tests
for FIFO draining, re-entrant completion attempts, and failure isolation.

**Manual test second**: open a batch of at least three scenarios with staggered
download completion. Verify downloads and opening overlap as intended, but
Results Analysis hand-offs never overlap or re-enter, and every successful
scenario is opened once.

## T004: Combined regression verification ✅

Run the gating scenario followed by the staggered multi-scenario serialization
scenario in one QGIS session. Record the manual UI paths and verify that no
changes were made to `../threedi-results-analysis`.
