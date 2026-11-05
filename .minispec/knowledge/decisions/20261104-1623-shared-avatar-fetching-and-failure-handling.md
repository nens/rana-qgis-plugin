---
type: decision
id: 20261104-1623-shared-avatar-fetching-and-failure-handling
date: 2026-11-04
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/api.py
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/workers/avatars.py
  - rana_qgis_plugin/widgets/utils_avatars.py
  - rana_qgis_plugin/widgets/processes_panel.py
  - rana_qgis_plugin/widgets/projects_selection_dialog.py
  - rana_qgis_plugin/widgets/file_info_dialog.py
tags: [avatars, cache, background-work, error-handling]
participants: [engineer, assistant]
---

# Share avatar fetching through the Loader cache and serial queue

## Context

The Loader already owns an `AvatarCache`, and several UI paths display user avatars. The cache stores initials placeholders as well as downloaded images, while the current `get_user_image()` helper does not distinguish an absent avatar from request failure. The avatar worker currently has no per-user failure result, and calling `Loader.fetch_avatars()` replaces/cancels the active worker. The Processes panel needs background avatar updates without disrupting other consumers.

The expected workload is small (about 10–20 users, with short requests), making serial background work adequate. The engineer accepts a later retry after failure and does not require separate per-user request bookkeeping or automatic retries.

## Options Considered

### Option 1: Keep placeholders only in Processes

Continue using `get_avatar_for_user()` without background retrieval.
- ✅ No scheduling or error handling changes.
- ❌ Process owners never transition to their remote avatar.
- ❌ Repeats behavior already known to differ from project selector and file info.

### Option 2: Reuse the shared cache with a cache-miss request path and serial queue

Store the placeholder synchronously before queuing a fetch; share cache updates/signals across consumers; distinguish no-avatar from failure and clear failed entries for a future retry.
- ✅ One shared cache and immediate placeholder display.
- ✅ Avoids repeat requests for users whose placeholder or remote avatar is already cached.
- ✅ New work does not cancel active work; simple scheduling fits the small expected volume.
- ❌ Requires clearer API result/error semantics and resilient worker signaling.

### Option 3: Add a separate avatar cache or concurrent per-consumer fetching

Give Processes its own cache or launch independent concurrent workers for each consumer.
- ✅ Consumer-local behavior can be isolated.
- ❌ Duplicates cached state and network work, making displayed avatars inconsistent.
- ❌ Unnecessary concurrency and lifecycle complexity for the expected request volume.

## Decision

Choose **Option 2**. Keep the Loader-owned `AvatarCache` shared by UI consumers. On a cache miss, synchronously cache and return the initials placeholder, then queue a background fetch. A placeholder cache hit suppresses duplicate fetch submission. Loader queues avatar work serially and does not cancel an active worker when new work arrives.

The API/worker outcome contract distinguishes:

- **Avatar found:** worker emits the image; cache replaces the placeholder and emits `avatar_changed(user_id)`.
- **No avatar** (for example, HTTP 404): keep the placeholder as the cached result.
- **Actual failure** (other request/server/transport failures or invalid image data): worker reports failure for that user, continues with other users, and the cache removes that user's entry without emitting `avatar_changed`.

Clearing on failure allows a later explicit request to retry. It does not trigger an immediate UI update/retry cycle, and there is no automatic retry policy. All consumers needing remote avatars use the shared request path.

This decision adds shared avatar loading as a cross-cutting refinement, rather than extending the Processes feature with a Processes-only avatar subsystem. It does not require changing the existing decision that names remain readable without avatars; it adds an optional shared enhancement.

## Consequences

### Positive

- ✅ Processes, project selector, and file-info views share one cache and receive consistent avatar updates.
- ✅ UI displays a placeholder immediately and remains responsive during requests.
- ✅ A failed request does not permanently pin a placeholder; a later request can retry.
- ✅ Missing avatars are normal and do not produce repeated requests during the cache lifetime.
- ✅ Serial queueing avoids cancellation races without adding per-user in-flight bookkeeping or concurrency controls.

### Negative

- ⚠️ API and worker contracts must preserve enough status/error context to distinguish absence from failure.
- ⚠️ A no-avatar placeholder remains cached for the cache lifetime; changes to a user's avatar are not discovered until cache lifecycle/reset or another explicit invalidation.
- ⚠️ A later retry only occurs when a consumer explicitly requests the avatar again.

## Code References

- Shared cache and placeholder creation: `rana_qgis_plugin/widgets/utils_avatars.py:AvatarCache`
- API image retrieval: `rana_qgis_plugin/utils/api.py:get_user_image`
- Background worker: `rana_qgis_plugin/workers/avatars.py:AvatarWorker`
- Loader scheduling and cache ownership: `rana_qgis_plugin/loader.py:Loader.fetch_avatars`
- Processes consumer: `rana_qgis_plugin/widgets/processes_panel.py:ProcessesPanel`
- Existing consumers: `rana_qgis_plugin/widgets/projects_selection_dialog.py`, `rana_qgis_plugin/widgets/file_info_dialog.py`

## Related Decisions

- `20261029-1107-processes-table-filters-details` — establishes the Processes table and its readable contributor fallback; the avatar enhancement remains optional to displaying names.

## Notes

The associated design is `.minispec/specs/feat_458_avatars/design.md`. During implementation, verify QGIS/Qt thread affinity for cache mutation and signal delivery, and ensure queued/active workers are safe during Loader shutdown.
