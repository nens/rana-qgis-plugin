---
feature: project-visibility-selection
branch: feat_425_project_selector
status: complete
created: 2026-08-03
decisions:
  - 20260803-1000-project-visibility-blocklist.md
  - 20260803-1001-project-visibility-storage.md
  - 20260803-1002-projects-selection-dialog.md
  - 20260803-1003-projects-selection-ux.md
---

# Project Visibility Selection

## Overview

Users can control which projects appear in the QGIS Browser's Rana root data item. Two interaction points:

1. **Per-project:** A "Don't show this project" context menu action on each `RanaProjectDataItem`
2. **Bulk:** A "Select projects" action on `RanaRootDataItem` that opens a `ProjectsSelectionDialog` where the user can see all projects (including currently hidden ones), filter them, and toggle visibility using checkboxes

Hidden project state is stored as a blocklist scoped per `(base_url, tenant_id)` pair, so switching tenant or backend maintains independent visibility settings.

## User Stories

- As a user, I want to hide individual projects I don't work on so the browser list stays manageable
- As a user, I want to bulk-manage project visibility in a filterable dialog so I can quickly re-show projects I've hidden
- As a user, I want my visibility preferences to survive QGIS restarts and tenant/backend switches

## Components

### `utils/project_visibility.py`

Manages reading and writing the hidden projects blocklist.

- `hidden_projects_file() -> Path` — returns `Path(QgsApplication.qgisSettingsDirPath()) / "rana" / "hidden_projects.json"`
- `get_hidden_projects(base_url: str, tenant_id: str) -> set[str]` — load hidden project IDs for the given scope
- `set_hidden_projects(base_url: str, tenant_id: str, hidden_ids: set[str]) -> None` — overwrite the hidden set for the given scope; uses atomic write (write to `.tmp`, rename)
- `hide_project(base_url: str, tenant_id: str, project_id: str) -> None` — convenience: add one ID to the hidden set
- `show_project(base_url: str, tenant_id: str, project_id: str) -> None` — convenience: remove one ID

The JSON structure:
```json
{
  "https://www.ranawaterintelligence.com|tenant-uuid": ["project-id-1", "project-id-2"]
}
```

Key format: `{base_url}|{tenant_id}`. The file is created on first write. Reads on a missing file return an empty set.

### `widgets/projects_selection_dialog.py`

A dialog for bulk project visibility management. Forked from `legacy/widgets/projects_browser.py` with the following changes:

**Kept from legacy:**
- `QTreeView` + `QStandardItemModel` for project display
- `FilterBar` with text search and contributor combo
- Client-side sort using `_SORT_KEYS`
- Contributor avatar display via `ContributorAvatarsDelegate` and `avatar_cache`
- `get_tenant_projects()` API call to fetch all projects

**Changed:**
- Wrapped in `QDialog` (not `QWidget`)
- **Pagination removed** — all projects loaded at once (filtered, but not paginated)
- **No "Open project" context menu** — replaced by checkbox-based selection
- Added checkbox column (or `Qt.CheckStateRole` on the name column) to each row
- Added toolbar buttons: **Check All**, **Uncheck All**
- Shift+click on checkboxes toggles a range
- Dialog initialized with the current hidden set pre-applied (visible projects = checked, hidden = unchecked)
- OK/Cancel buttons: OK writes the new hidden set via `set_hidden_projects()`

**Class:** `ProjectsSelectionDialog(QDialog)`

Constructor: `__init__(self, communication: UICommunication, parent=None)`

### `RanaProjectDataItem` — extended actions

Add to `actions(parent)`:
- "Don't show this project" action
  - Calls `hide_project(base_url(), get_tenant_id(), self._project_id)`
  - Calls `self.parent().refresh()` to trigger `createChildren()` again

### `RanaRootDataItem` — extended actions

Add to `actions(parent)` when authenticated:
- "Select projects" action
  - Instantiates `ProjectsSelectionDialog(self.communication, parent=None)`
  - On dialog accepted: calls `self.refresh()` to reload children with updated hidden set

### `RanaRootDataItem.createChildren()` — filtering

After fetching all projects from the API:
1. Load hidden set: `hidden = get_hidden_projects(base_url(), get_tenant_id())`
2. Filter: `items = [p for p in response["items"] if p["id"] not in hidden]`
3. Return `RanaProjectDataItem` for each non-hidden project

Thread safety: `get_hidden_projects()` reads a file; this is safe in a background thread since writes use atomic rename.

## Data Model

**Hidden projects file:** `{qgisSettingsDirPath}/rana/hidden_projects.json`

```json
{
  "{base_url}|{tenant_id}": ["project-id-1", "project-id-2"]
}
```

- `base_url`: full URL without trailing slash (e.g. `https://www.ranawaterintelligence.com`)
- `tenant_id`: UUID string of the tenant
- Project IDs: strings (UUIDs)

## User Flows

### Hide a single project
1. User right-clicks a project in the browser
2. Selects "Don't show this project"
3. Project ID added to hidden set → browser refreshes → project disappears

### Bulk manage via dialog
1. User right-clicks the Rana root item
2. Selects "Select projects"
3. Dialog opens showing all projects with checkboxes (visible = checked)
4. User filters by name/contributor, checks/unchecks
5. Clicks OK → hidden set updated → browser refreshes

## Open Questions

- Should the Rana root item show a status indicator (e.g. "12 projects, 3 hidden") somewhere? Deferred.
- Stale hidden IDs (projects deleted server-side) are silently ignored — they remain in the JSON but never match a fetched project. This is acceptable; no cleanup needed.

## Manual Testing Paths

- Right-click a project → "Don't show this project" → verify it disappears from browser
- Right-click Rana root → "Select projects" → verify dialog shows all projects including hidden ones
- Uncheck a project in dialog, click OK → verify it disappears; recheck, click OK → verify it reappears
- Hide a project, restart QGIS → verify it stays hidden
- Switch tenant → verify different hidden set applies
- Switch backend URL → verify different hidden set applies
