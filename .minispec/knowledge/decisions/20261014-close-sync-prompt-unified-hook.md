---
type: decision
id: 20261014-close-sync-prompt-unified-hook
date: 2026-10-14
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/close_sync_prompt.py
  - rana_qgis_plugin/rana_qgis_plugin.py
tags: [sync, dirty-tracking, project-close]
participants: [engineer, build agent]
---

# Single `aboutToBeCleared` Hook for Both Quit and Project-Close; Fire-and-Forget Sync

## Context

`20260818-1041-close-project-sync-prompt.md` already decided to hook
`QgsProject.instance().aboutToBeCleared` for a close-project sync warning, but
it was never implemented — `feat_454_open_generic_files` explicitly deferred
it. Picking it up now (`feat_470_file_sync`), two follow-on questions came up
during design: whether quitting QGIS needs its own additional hook for real
cancelability, and whether "Sync now" should block the close until upload
completes.

## Options Considered

### Option 1: Two hooks (mainWindow `QCloseEvent` for quit + `aboutToBeCleared` for project switch)

`QCloseEvent` is cancelable (`event.ignore()` genuinely stops QGIS from
quitting); `aboutToBeCleared` is not. Using both would give real "stay open"
capability specifically when quitting.
- ✅ Quitting specifically gets a real Cancel
- ❌ Quitting QGIS *also* fires `aboutToBeCleared` as part of its own shutdown
  sequence — both hooks fire for the same single quit action, requiring
  dedup logic to avoid nagging the user twice about the same dirty layers
- ❌ Two code paths to maintain for what is conceptually one concern

### Option 2: Single `aboutToBeCleared` hook for both quit and project-close

- ✅ One code path; no dedup logic needed since only one hook fires per action
- ✅ Consistent with the already-accepted decision's reasoning (no cancelable
  alternative exists for the general case; this was already an accepted
  limitation, just not yet extended to the quit scenario specifically)
- ❌ "Cancel" never means "stay open" — only "skip syncing now," even when
  quitting

### Blocking sync — considered and rejected

Initially considered having "Sync now" block the close with a progress
dialog + event loop, to guarantee the sync finishes before QGIS exits
(background `QgsTask`s aren't guaranteed to finish during app shutdown).
Rejected: blocking the UI for upload duration on every project-close or
quit — including routine, frequent actions — is worse UX than accepting that
a sync started at quit-time might occasionally not finish. Close-time sync
therefore reuses existing fire-and-forget methods. Indicator refresh relies
on `QgsMapLayer.customPropertyChanged` when the existing dirty properties are
set or removed; it does not add a Loader completion signal.

## Decision

We chose **Option 2** (single `aboutToBeCleared` hook) with **fire-and-forget
sync**, because quitting QGIS is a superset of closing the project (it clears
the project as part of its own shutdown), so a second hook adds a dedup
problem without adding real capability for the common case. "Sync now" reuses
the existing fire-and-forget `LayerTreeMenuProvider.save_style`/`save_data`
calls unchanged.

## Consequences

### Positive
- ✅ One hook, one code path, no dedup logic
- ✅ No new close-sync upload/locking/completion coordination — reuses
  existing sync entry points exactly as the context menu does
- ✅ No added wait time for routine project-close/quit actions

### Negative
- ⚠️ "Cancel" never truly aborts a close/quit, even when quitting — the
  dialog must not offer a button implying it can
- ⚠️ A sync started via "Sync now" at quit time may not finish if QGIS exits
  first — accepted as a best-effort tradeoff, not solved

## Related Decisions

- `20260818-1041-close-project-sync-prompt.md` (original proposal, now
  implemented by this decision)
- `.minispec/specs/feat_470_file_sync/design.md`
