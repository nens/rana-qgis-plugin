# Decision: Open the latest schematisation revision

- **Date:** 2026-08-31
- **Status:** accepted

## Context

Opening a Rana schematisation requires resolving schematisation metadata and a
revision before using the existing revision downloader. A local WIP may also
exist and must not be silently discarded.

## Decision

Resolve and open the latest remote revision by default, while retaining the
existing WIP decision logic to determine whether it replaces the local revision
or creates a new WIP.

## Rationale

This gives predictable behavior for a browser open while preserving local work
and the established legacy semantics for WIP handling.

## Consequences

The open request must resolve latest-revision metadata and local paths before
downloading. WIP selection/replacement remains part of the open flow rather
than becoming a separate user operation.
