# Loader-owned simulation preflight

## Status

Accepted

## Context

The context-menu item should not own API calls or simulation prerequisite
branching. The existing loader already owns simulation startup.

## Decision

Add a loader entry point that resolves the latest revision, checks model state,
and either delegates to the existing simulation startup, guides the user to
Processes or Version history, or offers model creation.

## Consequences

The data item only wires the action and supplies a Version history callback.
The preflight currently performs its click-time API calls synchronously.
