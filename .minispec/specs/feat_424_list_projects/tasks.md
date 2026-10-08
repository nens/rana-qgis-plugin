---
feature: feat_424_list_projects
status: complete
created: 2026-08-03
chunk_size: adaptive
total_tasks: 4
estimated_lines: 135
---

# List Projects in QGIS Browser — Tasks

## Overview

Implements project listing as children of `RanaRootDataItem` in the QGIS Browser panel.
Projects are fetched via QGIS built-in `createChildren()` (background thread), refreshed
manually via context menu and automatically on OS focus-regain.

See design: `../20260803-081059-now-login-rana/design.md`

## Task List

### Foundation

#### Task 1: Refactor `get_tenant_projects` error handling
- **Estimate:** ~15 lines
- **Files:** `rana_qgis_plugin/utils/api.py`
- **Description:** Drop `communication` parameter from `get_tenant_projects`. Raise
  `FetchError` on failure instead of swallowing the exception. Update any other callers
  of the old signature.
- **Depends on:** None
- **Acceptance:** `get_tenant_projects` has no `communication` param; raises `FetchError`
  on network failure; no other callers pass `communication`.
- **Evidence:** Unit tests pass; grep confirms no remaining calls with `communication` arg.

### Core Implementation

#### Task 2: Add `RanaProjectDataItem` and wire `createChildren()`
- **Estimate:** ~50 lines
- **Files:** `rana_qgis_plugin/data_items/rana_item.py`
- **Description:** 
  - Add `RanaProjectDataItem` — minimal `QgsDataItem` subclass with `project_id` and
    `name`; path and icon set; no children.
  - Add `createChildren()` to `RanaRootDataItem`: fetch projects via `get_tenant_projects`,
    return `[]` if not authenticated, catch `FetchError` and report via
    `self.communication.show_error`, return list of `RanaProjectDataItem`.
  - Remove `setState(Populated)` from `__init__`; instead set it only when not
    authenticated, so QGIS uses deferred loading when logged in.
  - Add manual Refresh action to `actions()` when authenticated.
- **Depends on:** Task 1
- **Acceptance:** Expand root item after login → projects listed by name. Expand when
  not logged in → empty, no error. API error → message bar shown.
- **Evidence:** Manual test: log in, expand Rana root item, project names visible.

#### Task 3: Focus-regain auto-refresh in `RanaQgisPlugin`
- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/rana_qgis_plugin.py`
- **Description:**
  - `RanaDataItemProvider` stores a reference to the root item created in `createDataItem`.
  - `RanaQgisPlugin` installs an event filter on the main window in `initGui`.
  - Event filter uses `externally_deactivated` guard (from legacy commit b96a29e):
    set flag on `WindowDeactivate` only when `QApplication.activeWindow() is None`;
    call `root_item.refresh()` on `WindowActivate` only if flag was set.
  - Clean up event filter in `unload`.
- **Depends on:** Task 2
- **Acceptance:** Switch to external OS app and back → project list refreshes. Open/close
  a QGIS dialog → no refresh triggered.
- **Evidence:** Manual test: add a project remotely, alt-tab away and back, project appears.

### Verification

#### Task 4: E2E test — project listing
- **Estimate:** ~40 lines
- **Files:** `e2e/test_datasource.py` (new)
- **Description:** E2E test using `qtbot` that:
  - Logs in via the datasource root item (reuse login helpers from conftest if available)
  - Expands the root item and verifies at least one `RanaProjectDataItem` child appears
  - Verifies the child item displays a project name
- **Depends on:** Task 2
- **Acceptance:** Test passes against a real Rana backend in CI.
- **Evidence:** CI E2E test run passes.
- **Note:** E2E test permission explicitly granted for this feature.

## Notes

- `RanaProjectDataItem` exposes `project_id` attribute for future project selector
  persistence (store in `QgsSettings` by `id`).
- Focus-regain logic in `RanaQgisPlugin` is intentionally generic — it will serve file
  listing and other future child item types without changes.
- `addChildItem()` is available for future "add project" action without triggering a
  full refresh; no custom mechanism needed.
- Incremental fetch via `order_by=updated_at` is a documented future optimisation once
  confirmed to work on the API. See decision `20260803-0812-project-fetch-strategy`.

## Progress

- [x] Task 1: Refactor `get_tenant_projects` error handling
- [x] Task 2: Add `RanaProjectDataItem` and wire `createChildren()`
- [x] Task 3: Focus-regain auto-refresh in `RanaQgisPlugin`
- [x] Task 4: E2E test — project listing
