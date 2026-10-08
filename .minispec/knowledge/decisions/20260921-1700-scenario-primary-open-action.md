---
id: 20260921-1700-scenario-primary-open-action
date: 2026-09-21
status: accepted
---

# Scenarios use the primary Open in QGIS action

## Context

Scenario results are downloaded and automatically opened in Results Analysis.
The current file action list had a separate `Download results` action for
scenarios, while multi-select and folder operations use the generic `Open in
QGIS` action. This created two names for the same user intent and required
special action-name injection in multi-select gating.

## Decision

Scenarios use `FileAction.OPEN_IN_QGIS` as their primary open action, just
like vectors, rasters, and schematisations. The action is routed by file or
request type:

- a single scenario opens through `Loader.open_scenario_results()` and uses
  interactive result selection;
- a scenario in a multi-select or folder operation becomes an
  `OpenScenarioRequest` and uses `Loader.open_scenario_results_batch()` with
  fixed defaults.

There is no separate current-loader `DOWNLOAD_RESULTS` action. `OPEN_WMS`
remains a separate scenario-specific action.

## Consequences

- Single scenarios have one primary open action and no duplicate download
  action.
- Multi-select action intersection can use the actual `QAction` list without
  inventing action names.
- Downstream behavior is selected by typed request dispatch, not by action
  label parsing.

## Related Decisions

- `20260831-1500-scenario-results-batch-selection`
- `20260921-1600-scenario-results-automatic-loading`
