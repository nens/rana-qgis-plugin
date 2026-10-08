# Decision: Pre-flight failures use modal show_warn/show_error, not the message bar

**ID:** 20261001-1400-simulation-preflight-errors
**Date:** 2026-10-01
**Status:** Accepted

## Context

Before any dialog opens, `Loader.start_simulation` performs pre-flight
checks: working directory configured, at least one 3Di organisation
available, and an enabled+valid 3Di model found for the revision. These can
fail even though the button was enabled (e.g. the model was disabled
server-side after the row was fetched).

## Decision

Surface pre-flight failures via `communication.show_warn` / `show_error`
(modal dialogs), not `bar_warn` / `bar_error` (message bar).

## Reasoning

- These are blocking conditions that prevent the entire flow from starting
  at all — the user needs to notice and acknowledge them, similar to how
  other blocking pre-conditions in the codebase (e.g. missing working
  directory in `save_revision`) use modal communication.
- The message bar is better suited to transient/background-task feedback
  (uploads, downloads), not a direct response to a button click that did
  nothing.

## Consequences

Consistent with `save_revision`'s existing `bar_error`/modal split: blocking
pre-conditions get a modal, background task outcomes get the message bar.
