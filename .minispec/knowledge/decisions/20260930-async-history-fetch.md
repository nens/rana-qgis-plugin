---
type: decision
id: 20260930-async-history-fetch
date: 2026-09-30
status: accepted
supersedes: 20260928-1812-fetch-all-generic-history
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/version_history_dialog.py
tags: [file-history, qt, qgstask, performance]
participants: [engineer, implementation-agent]
---

# Fetch History Off the GUI Thread

## Context

The initial history implementation fetched all generic history pages
synchronously. In manual use, long histories made the dialog noticeably slow
and blocked the QGIS UI while network requests and row preparation completed.
The same complete-fetch requirement applies to schematisation revisions,
because model-limit button state depends on the full revision list.

## Decision

History fetching will run in a `QgsTask` rather than on the GUI thread. Generic
history is fetched one cursor page per task; the first page is loaded with a
limit of 100 and later pages are requested when the user reaches the table
scrollbar bottom. Task workers return plain row batches. `QStandardItem`
creation and all model/widget updates remain on the GUI thread in task signal
handlers.

The shared dialog will disable Refresh while a fetch is active, show an
explicit loading state, route worker errors through the existing API error
signals and inline error label, and ignore stale completion results from an
older refresh. Closing the dialog cancels the active task and prevents its
result from updating the closed dialog.

The API wrappers retain their current synchronous function contracts. The
task boundary is owned by the dialog layer so existing callers are unchanged.

## Consequences

- ✅ Long network fetches no longer block the QGIS GUI thread.
- ✅ Qt objects are created and mutated only on the GUI thread.
- ✅ Complete eager aggregation and exact revision model counts are retained.
- ⚠️ Refresh and close lifecycle requires task identity and cancellation
  handling.
- ⚠️ The implementation must preserve the current error signal semantics.
- ⚠️ The backend can incorrectly return `next: null` for a full page while
  additional history exists; cursor correctness is tracked with the backend
  team and cannot be repaired reliably by the client because the cursor is
  opaque.

## Related Decisions

- `20260928-1812-fetch-all-generic-history`
- `20260928-1808-revision-button-enablement`
- `20260928-1823-history-dialog-base-and-siblings`
