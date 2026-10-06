# Browser Filters Design

**Date:** 2026-05-04  
**Status:** Designed, pending implementation plan

---

## Overview

Add filter bars to the ProcessesBrowser, FilesBrowser, and PublicationsBrowser, and extend the existing ProjectsBrowser filter with a Status filter. All four browsers will share a common `FilterBar` widget pattern. Filtering is entirely client-side (no API search parameters).

---

## Motivation

The ProjectsBrowser already has Name and Who filters. The feature request is to:
- Add a **Status** filter to ProjectsBrowser
- Add **Name, Who, Status** filters to ProcessesBrowser
- Add **Name, Type** filters to FilesBrowser
- Add **Name, Who** filters to PublicationsBrowser

---

## Filter Configurations Per Browser

| Browser | Name (text) | Who (multi-select) | Status (multi-select) | Type (multi-select) |
|---|---|---|---|---|
| ProjectsBrowser | existing | existing → replace with `QgsCheckableComboBox` | new, fixed values | — |
| ProcessesBrowser | new | new, dynamic from job list | new, fixed values | — |
| FilesBrowser | new | — | — | new, dynamic from file list |
| PublicationsBrowser | new | new, dynamic from publication list | — | — |

### Status values

- **ProjectsBrowser:** `active`, `archived` (from `ProjectStatus` enum)
- **ProcessesBrowser:** `scheduled`, `pending`, `running`, `completed`, `failed`, `cancelled`, `crashed`, `paused`, `cancelling` (from `JobStatus` enum)

### Dynamic combo population

- **Who (ProcessesBrowser):** populated from `creator` fields of loaded jobs
- **Who (PublicationsBrowser):** populated from `creator` fields of loaded publications
- **Type (FilesBrowser):** populated from `data_type` fields of loaded files; `null` data_type shown as "Unknown"

---

## UI Layout

Each browser gets a horizontal filter bar (`QHBoxLayout`) above the tree view, consistent with the existing ProjectsBrowser layout:

```
[ 🔍 Search by name ] [ Who ▼ ] [ Status ▼ ] [ ↺ ]
```

Files browser:
```
[ 🔍 Search by name ] [ Type ▼ ] [ ↺ ]
```

The refresh button stays in the filter bar row.

### Widgets

- **Name search:** `QLineEdit` with placeholder text, triggers filtering on `textChanged`
- **Combo filters:** `QgsCheckableComboBox` (built-in QGIS multi-select combo)
  - `setDefaultText("All contributors")` / `"All statuses"` / `"All types"` when nothing selected
  - Items added with `addItem(QIcon(avatar), display_name, userData=id)` for Who filters — avatars display natively alongside checkbox, no custom delegate needed
  - `checkedItemsData()` returns list of selected `userData` values
  - Triggers filtering on `checkedItemsChanged`
- **Refresh button:** `QToolButton` with refresh icon, unchanged

---

## Shared `FilterBar` Widget

A new `FilterBar(QWidget)` class in `rana_qgis_plugin/widgets/filter_bar.py`.

### Responsibilities

- Constructs and lays out filter widgets based on a config passed at construction
- Emits `filters_changed(dict)` signal whenever any filter changes
- Provides `get_filters() -> dict` returning current values
- Provides `set_combo_items(filter_key, items)` for dynamic population of combo filters
- Provides `update_combo_avatar(filter_key, user_id, avatar)` for async avatar updates

### Config format

```python
FilterBar(
    filters=[
        TextFilterConfig(key="name", placeholder="Search by name"),
        ComboFilterConfig(key="who", placeholder="All contributors", dynamic=True),
        ComboFilterConfig(key="status", placeholder="All statuses", dynamic=False,
                         items=[("Active", "active"), ("Archived", "archived")]),
    ],
    refresh_callback=self.refresh,
    parent=self,
)
```

### Signal output format

```python
# filters_changed emits a dict, e.g.:
{
    "name": "flood",          # str, empty string means no filter
    "who": ["uuid1", "uuid2"],  # list of userData values, empty list means no filter
    "status": ["active"],     # list, empty means no filter
}
```

---

## Filtering Logic (per browser)

Each browser keeps its own `_apply_filters(filters: dict)` method. The `FilterBar` only reports values; it has no knowledge of data structures.

Each browser connects:
```python
self.filter_bar.filters_changed.connect(self._apply_filters)
```

### ProcessesBrowser, FilesBrowser, PublicationsBrowser

These browsers have no pagination. Row visibility is toggled via `QTreeView.setRowHidden()` — all rows stay in the model, no re-population needed. Filter logic is ~10-15 lines per browser.

```python
def _apply_filters(self, filters):
    name = filters.get("name", "").lower()
    who = filters.get("who", [])
    status = filters.get("status", [])

    root = self.model.invisibleRootItem()
    for row in range(root.rowCount()):
        item = root.child(row, 0)
        job: JobData = item.data(Qt.UserRole)
        visible = True
        if name and name not in job.name.lower():
            visible = False
        if who and job.user["id"] not in who:
            visible = False
        if status and job.status not in status:
            visible = False
        self.tree_view.setRowHidden(row, QModelIndex(), not visible)
```

### ProjectsBrowser

ProjectsBrowser has **pagination**, which is incompatible with `setRowHidden()` — the paginated slice must be computed from the filtered set, not the full model. The existing approach is preserved:

- `filter_projects()` rebuilds `self.filtered_projects` (a filtered Python list)
- `populate_projects()` clears and re-populates the model from the paginated slice of `filtered_projects`
- The `FilterBar` replaces the inline widgets and emits `filters_changed`; `_apply_filters()` translates the dict into the existing `filter_projects()` call

Pagination removal is out of scope for now and may be addressed in a future change.

## Out of Scope

- Server-side filtering (API does not support it for these endpoints)
- Pagination interaction (ProjectsBrowser pagination resets to page 1 on filter change — existing behaviour preserved)
- Saving/restoring filter state between sessions

---

## Open Questions

- Should the filter bar be visible by default, or collapsed until activated? (Current assumption: always visible, consistent with ProjectsBrowser)
- FilesBrowser navigates directories — filters apply only to items in the current directory view (no deep search across directories)
