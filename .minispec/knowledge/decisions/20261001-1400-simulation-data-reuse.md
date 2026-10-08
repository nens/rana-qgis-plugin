# Decision: Reuse in-memory revision data; skip background prefetch

**ID:** 20261001-1400-simulation-data-reuse
**Date:** 2026-10-01
**Status:** Accepted

## Context

Legacy's `Loader.start_simulation` re-fetched `get_threedi_schematisation()`
and `fetch_schematisation_revision()` before opening `ModelSelectionDialog`,
even though `SchematisationRevisionHistoryDialog.fetch_page()` already
fetched the full revision list (including `schematisation_id`,
`schematisation_name`, `management_url`, and each `revision` object) to
render the history table. Two network calls remain unavoidable regardless:
`get_threedi_organisations()` + `fetch_organisations(...)` and
`fetch_schematisation_revision_3di_models(...)` (to find the currently
active model, needed by `ModelSelectionDialog`).

## Decision

`Loader.start_simulation` reuses `row.metadata` from the history dialog
instead of re-fetching schematisation/revision data. It still performs the
2 unavoidable synchronous calls before opening the first dialog. No
background prefetch of organisations while the history dialog loads.

## Reasoning

- Removing the 2 redundant calls already removes meaningful latency without
  added complexity.
- Background prefetching would add state management (what if the dialog
  closes before prefetch completes? what if revisions are refreshed in the
  meantime?) for a relatively small additional latency win. Revisit only if
  the remaining 2-call latency proves to be a real problem in practice.

## Consequences

Slightly faster "Simulation" click-to-dialog time than legacy, with no new
background task/state to manage.
