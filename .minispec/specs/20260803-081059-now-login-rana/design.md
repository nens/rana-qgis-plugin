# Feature Specification: List Projects in QGIS Browser

**Feature Branch**: `20260803-081059-now-login-rana`
**Created**: 2026-08-03
**Status**: Complete
**Decisions**:
  - [20260803-0810-project-child-population](../../knowledge/decisions/20260803-0810-project-child-population.md)
  - [20260803-0811-project-refresh-triggers](../../knowledge/decisions/20260803-0811-project-refresh-triggers.md)
  - [20260803-0812-project-fetch-strategy](../../knowledge/decisions/20260803-0812-project-fetch-strategy.md)
  - [20260803-0813-project-fetch-error-handling](../../knowledge/decisions/20260803-0813-project-fetch-error-handling.md)

## Overview

After logging in to Rana, the QGIS Browser panel should show the user's projects as
children of `RanaRootDataItem`. The list populates in the background without blocking
QGIS, stays fresh via manual refresh and automatic refresh on OS focus-regain, and is
structured to support a future interactive project selector with persistent selection.

---

## User Stories

### User Story 1 — View projects after login (Priority: P1)

After logging in, the user expands the Rana root item in the Browser panel and sees
their projects listed as child items, each showing the project name.

**Why this priority**: Core deliverable — without this, the feature does not exist.

**Independent Test**: Log in, expand the Rana root item, verify project names appear
without QGIS freezing.

**Acceptance Scenarios**:

1. **Given** the user is logged in, **When** they expand the Rana root item,
   **Then** their projects are listed as child items with the project name visible.
2. **Given** the user is logged in, **When** they expand the Rana root item,
   **Then** QGIS remains responsive while projects are being fetched.
3. **Given** the API returns an error, **When** the user expands the root item,
   **Then** an error message is shown in the QGIS message bar and no crash occurs.

---

### User Story 2 — Manual refresh (Priority: P2)

The user can manually trigger a refresh of the project list from the context menu
on the Rana root item.

**Why this priority**: Needed for the user to pull in changes without leaving and
returning to QGIS.

**Independent Test**: Add a project via the Rana web UI, right-click the root item,
select Refresh, verify the new project appears.

**Acceptance Scenarios**:

1. **Given** a new project was added remotely, **When** the user triggers manual
   refresh, **Then** the new project appears in the list.
2. **Given** the list is already populated, **When** the user triggers manual
   refresh, **Then** unchanged projects are not visibly removed and re-added.

---

### User Story 3 — Automatic refresh on focus-regain (Priority: P2)

When the user switches away from QGIS to an external application and returns, the
project list automatically refreshes.

**Why this priority**: Improves discoverability of remote changes without user action;
same mechanism will serve future child item types.

**Independent Test**: Add a project remotely, switch to another OS application, switch
back to QGIS, verify the new project appears without manual refresh.

**Acceptance Scenarios**:

1. **Given** a new project was added remotely, **When** the user returns to QGIS from
   an external application, **Then** the project list refreshes automatically.
2. **Given** the user opens a QGIS-internal dialog and closes it, **When** focus
   returns to QGIS, **Then** no automatic refresh is triggered.

---

### Edge Cases

- API is unreachable: show error via message bar, leave existing children in place
  (do not clear the list on error).
- User is not authenticated when `createChildren()` runs: return empty list, no error
  shown (login flow handles this state separately).
- Zero projects returned: root item shows no children (no placeholder item needed).

---

## Requirements

### Functional Requirements

- **FR-001**: Projects MUST be fetched in the background; QGIS UI MUST remain
  responsive during fetch.
- **FR-002**: Each project MUST be represented as a child `QgsDataItem` under
  `RanaRootDataItem`, displaying the project name.
- **FR-003**: `get_tenant_projects` MUST raise `FetchError` on failure instead of
  accepting a `communication` parameter.
- **FR-004**: `createChildren()` MUST catch `FetchError` and report it via
  `self.communication.show_error(...)`.
- **FR-005**: On refresh, unchanged projects MUST NOT be visibly removed and
  re-added (QGIS built-in diff handles this).
- **FR-006**: A manual refresh action MUST be available on the root item context menu.
- **FR-007**: An automatic refresh MUST trigger when QGIS regains OS-level focus,
  but NOT when a QGIS-internal dialog closes.
- **FR-008**: Focus-regain logic MUST live in `RanaQgisPlugin`, not in the data item.
- **FR-009**: `RanaDataItemProvider` MUST retain a reference to the created root item
  so `RanaQgisPlugin` can call `refresh()` on it.

### Key Entities

- **Project**: Represents a Rana project. Key attributes from API: `id` (stable
  unique identifier, suitable for persisting selection), `name`, `code`, `slug`,
  `created_at`, `updated_at`, `status`.
- **RanaProjectDataItem**: New `QgsDataItem` subclass representing a single project
  in the Browser tree. Holds the project `id` and `name` at minimum.

### Future Considerations (not in scope)

- **Project selector persistence**: Project `id` is the stable key for storing a
  user's selected project in `QgsSettings` between sessions. `RanaProjectDataItem`
  should expose `project_id` as an attribute to support this.
- **Single item insertion**: `addChildItem()` is available for inserting a project
  created via an "add project" action without triggering a full refresh.
- **Incremental fetch**: Once `order_by=updated_at` is confirmed to work on the
  `project_list` endpoint, refresh can be optimised to fetch only items with
  `updated_at` newer than the last fetch timestamp. See decision
  `20260803-0812-project-fetch-strategy` for the full incremental path.
- **File listing**: The same `createChildren()` pattern and focus-regain refresh
  mechanism will be reused for listing files under each project.

---

## Success Criteria

- **SC-001**: Projects appear in the Browser tree after login without QGIS freezing.
- **SC-002**: An error during fetch produces a message bar notification; no crash.
- **SC-003**: A new project added remotely becomes visible after manual refresh or
  returning to QGIS from an external application.
- **SC-004**: Opening and closing a QGIS dialog does not trigger a project list refresh.
