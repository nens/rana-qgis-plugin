# Decision: Refresh through a loader signal

**Date:** 2026-08-12
**Status:** Accepted

## Decision

The loader exposes an upload-refresh signal carrying the target folder path.
After the task completes, it emits that path. Folder data items refresh only
when the path matches and the item is currently populated.

## Reasoning

This avoids retaining a direct data-item reference in a long-running task and
avoids fetching collapsed or otherwise invisible nodes.
