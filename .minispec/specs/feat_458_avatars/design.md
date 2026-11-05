---
feature: feat_458_avatars
status: planned
created: 2026-11-04
decisions:
  - 20261104-1623-shared-avatar-fetching-and-failure-handling
---

# Shared Avatar Fetching and Failure Recovery

## Overview

Use the Loader's existing shared `AvatarCache` and background avatar worker to fetch user avatars on demand across plugin UI consumers. A cache miss immediately displays an initials placeholder and queues a fetch; successful results update the shared cache and notify views, while actual failures clear the placeholder cache entry so a later request can retry.

This is a cross-cutting avatar lifecycle refinement, not a Processes-only avatar subsystem. The Processes panel is an initial consumer; the project selector and file-info flows should continue to share the same cache and fetch coordination.

## User Scenarios & Testing

### User Story 1 - See remote avatars without blocking the UI (Priority: P1)

As a QGIS user, I want user avatars to load in the background so contributor and process-owner views show the real avatar when available without delaying the UI.

**Independent Test**: Open a UI that displays a user whose avatar is not cached; verify the initials placeholder appears immediately and is replaced when the request succeeds.

**Acceptance Scenarios**:

1. **Given** a user has no cache entry, **When** a UI requests the avatar, **Then** it immediately receives and displays the initials placeholder and a background request is queued.
2. **Given** a remote avatar is returned, **When** the worker completes, **Then** the shared cache stores the real avatar, emits `avatar_changed(user_id)`, and subscribed views refresh that user's displayed avatar.
3. **Given** a placeholder is already cached, **When** another consumer requests the same user before the fetch completes, **Then** it receives the placeholder and does not queue another fetch.

### User Story 2 - Recover from avatar request failures (Priority: P1)

As a QGIS user, I want a failed avatar request not to pin a placeholder in the cache forever, so a later request can try again.

**Independent Test**: Cause an avatar request to fail, then request that user's avatar again and verify a new fetch can be queued.

**Acceptance Scenarios**:

1. **Given** the endpoint reports that the user has no avatar (for example, HTTP 404), **When** the worker completes, **Then** the initials placeholder remains cached and no failure-driven retry is triggered.
2. **Given** a transport/server error or invalid image response occurs, **When** the worker handles it, **Then** it emits a failure result for that user, clears that user's cache entry without emitting `avatar_changed`, and continues processing other users.
3. **Given** a failed request has cleared the cache entry, **When** a consumer requests that avatar later, **Then** a placeholder is recreated and another background fetch can be queued.

## Components

### Shared `AvatarCache`

Keep one cache owned by the Loader and injected into consumers. The cache stores placeholders and remote pixmaps keyed by user ID. Add a cache-miss request path, coordinated with Loader, that returns an existing pixmap or creates the initials placeholder and queues a background fetch. Add an operation to remove an entry on actual failure. Removing an entry must not emit `avatar_changed`: the currently displayed placeholder remains valid, and emitting would risk a redraw immediately re-requesting the failed avatar.

Consumers that want remote avatars must use the shared cache/request path rather than calling `get_avatar_for_user()` alone. Existing cache-hit behavior remains immediate and synchronous.

### Loader and worker scheduling

Loader remains the owner of the shared cache and avatar work. Redesign avatar submission so new work is queued serially instead of canceling the active worker. The expected volume is small (roughly 10–20 users) and requests are short, so a serial queue is preferred over concurrent workers or a more elaborate priority scheduler. Requests for the same user are naturally suppressed while a placeholder or real avatar remains cached; no separate per-user request bookkeeping is planned.

Each worker reports success, no-avatar, or failure per user. A failure for one user must not prevent processing later users in the same worker. Preserve existing project-selector and file-info behavior while integrating them with the shared request path.

### Avatar API helper

Distinguish a legitimate no-avatar response from an actual request or image-processing failure. A not-found response is a normal no-avatar result. Other HTTP failures, transport errors, and invalid image payloads must be surfaced as failures with useful diagnostic context, rather than silently returning `None` or allowing an exception to terminate the worker.

### Processes panel integration

Use the Loader's shared cache/request path for process-owner avatars. Subscribe to the existing `avatar_changed(user_id)` notification and refresh the visible rows for that owner from the cache. Do not fetch on every row redraw; cache hits return immediately and only a cache miss schedules work.

## Data and Signal Flow

```text
UI requests user avatar
  -> shared cache hit: return cached pixmap
  -> cache miss: store initials placeholder, enqueue user fetch, return placeholder
  -> worker processes queued request
       -> remote image: avatar_ready(user_id, image)
            -> shared cache replaces placeholder and emits avatar_changed(user_id)
            -> subscribed views refresh
       -> no avatar: keep placeholder
       -> actual failure: emit per-user failure, remove cache entry, no avatar_changed
```

After a failure, an already displayed placeholder remains visible. A future explicit avatar request can retry; automatic immediate retries and retry timers are not part of this design.

## Requirements

- **FR-001**: Avatar lookup MUST return a cached pixmap immediately when one exists.
- **FR-002**: On a cache miss, the shared request path MUST cache and return an initials placeholder before queuing background retrieval.
- **FR-003**: Avatar work MUST be queued serially and MUST NOT cancel an active avatar worker when new work is submitted.
- **FR-004**: A successful remote image MUST replace the placeholder in the shared cache and notify subscribers through `avatar_changed`.
- **FR-005**: A no-avatar response MUST preserve the placeholder and MUST NOT be treated as a request failure.
- **FR-006**: An actual API, transport, or image-decoding failure MUST be reported per user and clear that user's cache entry without emitting `avatar_changed`.
- **FR-007**: A worker MUST continue processing other users after an individual user's failure.
- **FR-008**: Existing consumers that display remotely retrievable avatars MUST use the shared request path; no second avatar cache is introduced.

## Edge Cases

- Multiple consumers request the same uncached user before a queued worker completes: the synchronously cached placeholder prevents duplicate submissions.
- A worker handles a missing-avatar response: retain the placeholder as a negative result for the current cache lifetime; no automatic retry is attempted.
- A worker fails after the placeholder is displayed: clear only the cache entry; leave current UI unchanged until a later request or successful fetch causes a view update.
- One user in a batch fails: record/report that user's failure and continue the batch.
- The plugin shuts down with queued or active avatar work: worker lifecycle and signal delivery must not access destroyed UI or cache objects; verify against the existing Loader shutdown behavior during implementation.

## Success Criteria

- An uncached user's placeholder appears without waiting for network work, and a successful fetch updates all subscribed views using the shared cache.
- A missing avatar remains represented by the initials placeholder without being treated as an error.
- A real failure removes the cache entry and permits a later request to retry, without an automatic retry loop.
- Adding requests from the Processes panel does not cancel avatar work already requested by the project selector or file-info view.
- No duplicate cache is introduced, and normal avatar fetching remains serial.

## Manual UI Testing

Open the Processes panel and project selector with an uncached owner/contributor; verify a placeholder is immediate and each view updates after the remote avatar arrives. Reopen the project selector while avatar work is pending and verify the active work is not canceled. Test a user with no avatar and confirm the placeholder remains. Simulate a request failure, confirm no immediate retry or visual disappearance, then request the avatar again and confirm it can be fetched. Also exercise the file-info avatar path to ensure its existing behavior still uses the shared cache.

## Open Questions

- During implementation, confirm the API client's reliable way to distinguish HTTP 404 from other HTTP failures and to retain status/error details for the worker failure signal.
- Confirm whether invalid image bytes should be represented as an explicit decode failure (recommended) rather than as a no-avatar result.
