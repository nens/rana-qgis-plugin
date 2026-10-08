# Decision: Always show Save revision for schematisation groups

- **Date:** 2026-08-31
- **Status:** accepted

## Context

Determining whether any layer in a schematisation has unsaved edits would add
state tracking across the layer tree and editor integration.

## Decision

Always expose **Save revision** for identified schematisation layer groups. The
save flow determines whether there is anything to upload and treats a no-op as
valid completion.

## Rationale

This keeps the UI discoverable and avoids duplicating edit-state ownership. The
existing save workflow already has the information needed to validate and
upload a revision.

## Consequences

The group must retain enough schematisation and revision metadata to start the
save flow. The action may perform a no-op when nothing changed.
