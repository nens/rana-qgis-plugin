# Synchronous Context Menu Operations

**Date:** 2026-08-17
**Status:** Accepted

## Context

We needed to decide whether rename, delete folder, and create folder should run
as background QgsTask instances (like uploads) or synchronously on the main thread.

The concern was preventing conflicting operations (e.g. renaming an item being deleted).

## Decision

Keep all three operations synchronous (blocking UI during the POST call).

## Rationale

- These are fast POST calls (~200-500ms), acceptable UI blocking
- Synchronous execution eliminates ALL concurrency issues by design
- No QgsTask, no signals to manage, no state tracking for in-flight operations
- Dramatically simpler code vs. the background task approach attempted in feat_451_with_tasks
- Upload remains async (QgsTask) because it involves S3 PUT which can take minutes

## Consequences

- UI freezes briefly during API calls (acceptable for <1s operations)
- No progress indicator needed (too fast to matter)
- No need for operation locking/guards on tree items
- The unused DeleteTask in workers/delete.py can be removed
