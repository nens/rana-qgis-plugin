---
id: 20260921-1600-scenario-results-automatic-loading
date: 2026-09-21
status: accepted
---

# Results Analysis loading is automatic, not confirmation-gated

## Context

The current `_add_layer_from_scenario` (`layer_management/layer_manager.py:126-157`)
asks the user "Do you want to add the results of this simulation to the
current project so you can analyse them with Results Analysis?" before
calling `ra_tool.load_result(...)`. `feat_455_open_results` moves scenario
downloading to the current `Loader`/`QgsTask` architecture and needed to
decide whether this confirmation prompt is preserved.

## Decision

Results Analysis loading is automatic after a successful scenario download,
for both the single-scenario and batch/folder flows. The existing
confirmation prompt is removed. There is no point in downloading a
scenario's results without opening them.

The existing compatibility behavior is unchanged: `load_result(...)` is
called with `project=...` where supported, falling back to the two-argument
call with a warning on `TypeError` for older Results Analysis versions, and a
warning (no exception) if Results Analysis is unavailable at all.

## Reasoning

Downloading results without opening them serves no purpose for the user;
the confirmation step only added friction. Removing it also simplifies the
single-scenario and batch flows to the same "download → open" pipeline,
consistent with decision `20260831-1500`'s per-scenario dispatch model.

## Consequences

- `Loader`'s extracted Results Analysis call (replacing
  `_add_layer_from_scenario`) invokes `ra_tool.load_result(...)` directly on
  successful download, with no `communication.ask(...)` step.
- Users who do not want a scenario's results loaded into the project must
  avoid triggering the download-results action, rather than declining a
  prompt afterward.
- FR-007 in `feat_455_open_results/design.md` is updated to state this
  explicitly.

## Related Decisions

- `20260831-1500-scenario-results-batch-selection`
