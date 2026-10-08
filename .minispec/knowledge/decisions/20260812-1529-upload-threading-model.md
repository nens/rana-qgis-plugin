# Decision: QgsTask for background file upload

**Date:** 2026-08-12
**Status:** Accepted

## Context

The slow upload PUT must not block QGIS. Legacy `FileUploadWorker` and
`ExistingFileUploadWorker` also wait for UI decisions from worker threads.

## Decision

Port both worker classes into new non-legacy code, but split their use into
main-thread preparation and a single cancellable `QgsTask` for the slow work.
Conflict decisions are completed before task submission. The new-file worker
is used now; the existing-file worker is prepared for a future layer-panel
feature.

## Reasoning

- `QgsTask` provides native progress, cancellation, ownership, and a
  main-thread `finished()` callback.
- Prechecking avoids reproducing legacy polling and worker-thread UI waits.
- Keeping both worker concepts preserves the distinct semantics needed for new
  files versus re-uploaded files.

## Alternatives Rejected

- `QThread`: unnecessary lifecycle management and legacy-style polling.
- `QRunnable`: lacks native QGIS task progress and cancellation UI.
- `QNetworkAccessManager`: would require replacing the synchronous requests
  upload path and introduce a more complex callback state machine.
