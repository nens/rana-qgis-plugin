---
id: 20260831-1500-scenario-results-batch-selection
date: 2026-08-31
status: accepted
---

# Scenario result selection differs between individual and batch opens

## Context

The legacy scenario flow uses `ResultBrowser` for an individual download, while
`Loader.download_files` handles multi-file downloads non-interactively. Scenario
opening is being moved to the current `Loader` and `QgsTask` architecture, where
multi-select and folder-open operations share one download batch.

## Decision

Use `ResultBrowser` only for an individual scenario action. Any batch operation,
including a batch containing only one scenario alongside other requests, uses
defaults without a dialog:

- download raw `results.zip`;
- download the attached `max water depth (file)` result;
- do not generate raster results.

Unavailable scenarios are skipped and reported through the message bar; valid
items continue. Each successfully downloaded scenario is opened once in Results
Analysis after the shared task completes.

## Reasoning

Repeated dialogs make folder and multi-select operations impractical and do not
match the established legacy `download_files` behavior. A fixed default gives a
predictable, non-blocking batch operation while retaining full control for the
individual workflow.

## Consequences

- The loader must know whether it is preparing an individual request or a batch
  before constructing scenario downloaders.
- Scenario download completion is grouped by scenario directory rather than by
  individual result file, so Results Analysis is invoked once per scenario.
- Batch skips and failures are partial outcomes, not reasons to abort valid
  scenario downloads.

## Related Decisions

- `20260429-1102-results-downloader-non-interactive`
- `20260818-1041-download-task-symmetry`
