# Shared model creation flow

## Status

Accepted

## Context

The revision-history dialog and the new context-menu action both need to start
model creation and direct the user to Processes. Duplicating that flow would
allow the two entry points to diverge.

## Decision

Extract model-generation checks, tracker-process startup, job extraction and
Processes navigation into a loader helper. Return an outcome that lets callers
update entry-point-specific UI state.

## Consequences

The revision-history dialog keeps ownership of button and row presentation,
while the loader owns the shared operation and its result.
