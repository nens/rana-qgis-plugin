# Decision: Fetch scenario file descriptor lazily on right-click

**Date:** 2026-08-05
**Status:** Accepted

## Context

For scenario-type files, the context menu entries OPEN_WMS and DOWNLOAD_RESULTS depend on the file descriptor (specifically `descriptor.meta.id` and `descriptor.meta.simulation.software.id`). The descriptor is available via `GET /tenants/{tenant_id}/file-descriptors/{file_descriptor_id}`.

Two options:
- **A (lazy):** Fetch the descriptor when the user right-clicks, then show the menu
- **B (eager):** Fetch descriptors for all scenario files when building the file listing

## Decision

Option A — fetch on right-click.

## Reasoning

- Consistent with the lazy loading strategy adopted throughout this feature
- Users may never right-click a scenario file; eager fetching would waste API calls
- Simpler to implement
- If right-click latency becomes noticeable, switch to Option B without architectural changes

## Consequences

- Brief delay between right-click and menu appearing for scenario files
- Network or fetch errors during descriptor fetch must be handled gracefully (show partial menu or error message)
- **Optimization path:** pre-fetch descriptor alongside file listing if latency proves problematic
