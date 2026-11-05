---
feature: feat_458_avatars
status: planned
created: 2026-11-04
chunk_size: adaptive
total_tasks: 6
estimated_lines: 230
---

# Tasks: Shared Avatar Fetching and Failure Recovery

**Input**: `.minispec/specs/feat_458_avatars/design.md`
**Branch**: `feat_458_processes`

## Overview

Implement shared cache-miss avatar fetching through the Loader, with serial worker scheduling, clear distinction between no-avatar and actual failure, cache recovery after failure, and integration into the project selector, Processes panel, and File Info dialog. Keep tests with the implementation slices. Manual UI verification is required for the three consumers and worker lifecycle behavior.

## Task List

### Foundation

#### T001: Distinguish missing avatars from API failures

- **Estimate:** ~35–50 lines
- **Files:** `rana_qgis_plugin/utils/api.py`, `tests/utils/test_api.py` (new or existing)
- **Description:** Change `get_user_image()` to represent a legitimate no-avatar response (such as HTTP 404) separately from actual HTTP/server, connectivity, or invalid-image failures. Retain useful status/error context when raising. Add focused tests for the result contract, including successful image data, no-avatar, HTTP failure, connectivity failure, and invalid image response as feasible with the existing network/API test patterns.
- **Depends on:** None
- **Acceptance:** Callers can distinguish no-avatar from failures; failure context identifies the relevant HTTP status or network/decode error.
- **Evidence:** Python syntax parsing and pre-commit checks pass. Focused API tests were skipped at the engineer's request.

#### T002: Report worker outcomes and support cache removal

- **Estimate:** ~35–50 lines
- **Files:** `rana_qgis_plugin/workers/avatars.py`, `rana_qgis_plugin/widgets/utils_avatars.py`
- **Description:** Extend avatar worker signaling for per-user actual failures. Treat no-avatar as a normal result, emit successful images as today, and catch failures per user so the rest of the batch continues and `finished` is emitted. Add an `AvatarCache` operation to remove a user's entry without emitting `avatar_changed`.
- **Depends on:** T001
- **Acceptance:** A successful image emits ready; no-avatar preserves the placeholder; an actual failure is reported, does not stop later users, and permits cache removal without `avatar_changed`.
- **Evidence:** Python syntax parsing and `git diff --check` pass. Tests were omitted at the engineer's request.

### Shared Loader flow

#### T003: Queue cache-miss requests through Loader

- **Estimate:** ~45–65 lines
- **Files:** `rana_qgis_plugin/loader.py`, `tests/loader/test_avatar_fetching.py` (new)
- **Description:** Add the shared Loader request path: return an existing cached pixmap immediately; otherwise cache and return an initials placeholder before queueing that user for background retrieval. Redesign avatar submission to queue work serially on the existing single-thread pool without canceling the active worker. Connect success to `AvatarCache.update_avatar` and failure to cache removal. Keep the existing `avatar_updated` forwarding behavior. Replace/correct the old cancel-and-replace worker lifecycle while retaining safe shutdown behavior.
- **Depends on:** T001, T002
- **Acceptance:** Cache hits do not submit new work; cache misses return a placeholder immediately and submit work; submitting another request does not cancel active work; success updates the cache; failure clears the cache entry and a later explicit request can submit again.
- **Evidence:** Existing Loader shutdown and Processes dock tests pass after the Loader changes; syntax parsing and pre-commit checks pass. New tests were omitted at the engineer's request. Successful image responses are now validated as decoded `QImage` values; endpoint metadata that returns a non-image type raises an explicit `RanaFetchError`.

### Consumer integrations

#### T004: Use shared avatar requests in the project selector [P]

- **Estimate:** ~25–40 lines
- **Files:** `rana_qgis_plugin/widgets/projects_selection_dialog.py`, `rana_qgis_plugin/loader.py`
- **Description:** Deduplicate contributors by ID after fetching projects and submit the unique users once through `Loader.get_avatars_for_users()`. The Loader returns cached avatars/placeholders and queues only cache misses as a batch. Preserve the existing `avatar_updated` handling for contributor rows and the filter combo. Ensure selector reopening/refreshing does not cancel existing avatar work.
- **Depends on:** T003
- **Acceptance:** Contributors display a placeholder immediately and update on `avatar_updated`; reopening or repopulating the selector does not cancel existing avatar work.
- **Evidence:** Project pre-commit checks pass. No focused selector test suite exists, and tests were omitted at the engineer's request. Manual: open/reopen the project selector while an avatar fetch is pending and verify the eventual update is received.

#### T005: Show and refresh process-owner avatars [P]

- **Estimate:** ~25–40 lines
- **Files:** `rana_qgis_plugin/widgets/processes_panel.py`, `rana_qgis_plugin/loader.py`, `tests/widgets/test_processes_panel.py`
- **Description:** Pass the shared Loader request callback/path into `ProcessesPanel`, request owner avatars through it, and listen for `avatar_updated` to refresh only rows belonging to that owner from the shared cache. Do not enqueue fetches during row redraws when a cache entry exists.
- **Depends on:** T003
- **Acceptance:** Process owner cells show cached or placeholder images immediately and update to the remote avatar when the cache signal arrives; unrelated owner rows are not changed.
- **Evidence:** Existing Processes-panel, Loader shutdown, and Processes dock tests pass (28 tests); pre-commit checks pass. Manual: open the panel with an uncached owner and verify its avatar updates after retrieval.

#### T006: Move File Info onto the shared request path [P]

- **Estimate:** ~25–40 lines
- **Files:** `rana_qgis_plugin/data_items/file_item.py`, `rana_qgis_plugin/widgets/file_info_dialog.py`, related file-info tests (add or update in the existing test location)
- **Description:** Pass Loader into File Info through the existing file-opening path. Replace the synchronous remote avatar lookup with the shared cache/request path, display the immediate placeholder or cache hit, and update the avatar label when `avatar_updated` arrives for the author. Preserve the dialog's existing metadata fetch and error behavior.
- **Depends on:** T003
- **Acceptance:** File Info no longer performs a synchronous avatar network request; it displays cached/placeholder avatar immediately and applies a later update for the matching author.
- **Evidence:** Existing File Info model and File Item tests pass (34 tests); pre-commit checks pass. No dialog-specific tests exist. Manual: open File Info for an uncached author and verify immediate display followed by the remote avatar update.

## Dependencies & Execution Order

- T001 precedes T002 because the worker requires distinct no-avatar and failure outcomes.
- T002 precedes T003 because Loader needs worker failure signaling and cache removal.
- T003 precedes all consumer integrations because it establishes the shared request API and scheduling behavior.
- T004, T005, and T006 can be implemented in parallel after T003; each changes a separate consumer area, although T005 also touches Loader construction/wiring and should coordinate with T003's Loader changes.

## Complexity Check

- No new cache or standalone avatar subsystem is introduced; the work extends the existing API helper, worker, cache, Loader, and consumers.
- New test files are limited to API, worker/cache, and Loader behavior where no focused coverage currently exists; consumer tests should extend existing suites when available.
- No automatic retry timer, priority scheduler, or per-user request bookkeeping is included.

## Manual UI Testing

- Processes panel: verify immediate placeholder and later owner-avatar update.
- Project selector: reopen while work is pending and verify active/queued fetches are not canceled and contributor/filter avatars refresh.
- File Info: verify the placeholder appears without waiting for network work and the author avatar updates on completion.
- No-avatar response: verify initials remain. Actual failure: verify the placeholder remains visible with no immediate retry, then a later explicit request can retry.

## Progress

- [x] T001: Distinguish missing avatars from API failures (API tests skipped at engineer request)
- [x] T002: Report worker outcomes and support cache removal (tests omitted at engineer request)
- [x] T003: Queue cache-miss requests through Loader
- [x] T004: Use shared avatar requests in the project selector (manual UI verification pending)
- [x] T005: Show and refresh process-owner avatars (manual UI verification pending)
- [x] T006: Move File Info onto the shared request path (manual UI verification pending)
