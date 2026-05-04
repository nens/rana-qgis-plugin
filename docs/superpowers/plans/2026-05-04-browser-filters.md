# Browser Filters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a shared `FilterBar` widget and connect it to all four browser widgets (ProjectsBrowser, ProcessesBrowser, FilesBrowser, PublicationsBrowser), adding name/who/status/type filters per browser.

**Architecture:** A new `FilterBar(QWidget)` in `widgets/filter_bar.py` owns the filter UI (a `QLineEdit` for name search and `QgsCheckableComboBox` instances for categorical filters). It emits `filters_changed(dict)` on any change. Each browser connects to this signal and runs its own thin `_apply_filters(filters)` method. ProjectsBrowser keeps its existing `filtered_projects` + `populate_projects()` approach (due to pagination); the other three browsers use `QTreeView.setRowHidden()`.

**Tech Stack:** PyQt5 via `qgis.PyQt`, `QgsCheckableComboBox` from `qgis.gui`, `QgsApplication` for icons.

---

## File Map

| File | Action | Purpose |
|---|---|---|
| `rana_qgis_plugin/widgets/filter_bar.py` | **Create** | Shared `FilterBar` widget |
| `tests/test_filter_bar.py` | **Create** | Unit tests for `FilterBar` |
| `rana_qgis_plugin/widgets/projects_browser.py` | **Modify** | Replace inline filter widgets with `FilterBar`; add status filter |
| `rana_qgis_plugin/widgets/processes_browser.py` | **Modify** | Add `FilterBar` with name/who/status filters |
| `rana_qgis_plugin/widgets/files_browser.py` | **Modify** | Add `FilterBar` with name/type filters |
| `rana_qgis_plugin/widgets/publications_browser.py` | **Modify** | Add `FilterBar` with name/who filters |

---

### Task 1: Create `FilterBar` widget

**Files:**
- Create: `rana_qgis_plugin/widgets/filter_bar.py`

- [ ] **Step 1: Implement `FilterBar`**

Create `rana_qgis_plugin/widgets/filter_bar.py`:

```python
from dataclasses import dataclass, field
from typing import Callable, Optional

from qgis.gui import QgsCheckableComboBox
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from rana_qgis_plugin.icons import refresh_icon


@dataclass
class TextFilterConfig:
    key: str
    placeholder: str


@dataclass
class ComboFilterConfig:
    key: str
    placeholder: str
    dynamic: bool = True
    items: list[tuple[str, str]] = field(default_factory=list)
    # items format: list of (display_label, user_data)


class FilterBar(QWidget):
    filters_changed = pyqtSignal(dict)

    def __init__(self, filters: list, refresh_callback: Callable, parent=None):
        super().__init__(parent)
        self._refresh_callback = refresh_callback
        self._line_edits: dict[str, QLineEdit] = {}
        self._combos: dict[str, QgsCheckableComboBox] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        for config in filters:
            if isinstance(config, TextFilterConfig):
                widget = QLineEdit()
                widget.setPlaceholderText(config.placeholder)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                widget.textChanged.connect(self._emit_changed)
                self._line_edits[config.key] = widget
                layout.addWidget(widget)
            elif isinstance(config, ComboFilterConfig):
                widget = QgsCheckableComboBox()
                widget.setDefaultText(config.placeholder)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                if not config.dynamic:
                    for label, data in config.items:
                        widget.addItemWithCheckState(label, 0, userData=data)
                widget.checkedItemsChanged.connect(self._emit_changed)
                self._combos[config.key] = widget
                layout.addWidget(widget)

        self._refresh_btn = QToolButton()
        self._refresh_btn.setIcon(refresh_icon())
        self._refresh_btn.clicked.connect(self._refresh_callback)
        layout.addWidget(self._refresh_btn)

        self.setLayout(layout)

    def _emit_changed(self):
        self.filters_changed.emit(self.get_filters())

    def get_filters(self) -> dict:
        result = {}
        for key, widget in self._line_edits.items():
            result[key] = widget.text()
        for key, widget in self._combos.items():
            result[key] = widget.checkedItemsData()
        return result

    def set_combo_items(self, key: str, items: list[tuple[str, str, Optional[QIcon]]]):
        """Populate a dynamic combo. items: list of (label, user_data, icon_or_None)."""
        combo = self._combos[key]
        combo.blockSignals(True)
        combo.deselectAllOptions()
        # QgsCheckableComboBox has no clear(); remove all rows manually
        while combo.count():
            combo.removeItem(0)
        for label, data, icon in items:
            if icon:
                combo.addItemWithCheckState(label, 0, userData=data)
                combo.setItemIcon(combo.count() - 1, QIcon(icon))
            else:
                combo.addItemWithCheckState(label, 0, userData=data)
        combo.blockSignals(False)

    def update_combo_avatar(self, key: str, user_id: str, avatar):
        """Update avatar icon for a user entry in a combo."""
        combo = self._combos[key]
        for i in range(combo.count()):
            if combo.itemData(i) == user_id:
                combo.setItemIcon(i, QIcon(avatar))
                break
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose run --rm qgis pytest -v tests/test_filter_bar.py
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rana_qgis_plugin/widgets/filter_bar.py tests/test_filter_bar.py
git commit -m "Add FilterBar widget with text and checkable combo filters"
```

---

### Task 2: Connect `FilterBar` to `ProjectsBrowser`

Replace the inline `projects_search` (`QLineEdit`) and `contributor_filter` (`QComboBox`) with a `FilterBar`. Add a Status filter. Filtering logic is unchanged — `filter_projects()` still rebuilds `filtered_projects` and calls `populate_projects()`.

**Files:**
- Modify: `rana_qgis_plugin/widgets/projects_browser.py`

- [ ] **Step 1: Update imports**

In `projects_browser.py`, replace:
```python
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
```
with:
```python
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from rana_qgis_plugin.widgets.filter_bar import ComboFilterConfig, FilterBar, TextFilterConfig
```

- [ ] **Step 2: Replace filter widget setup in `setup_ui`**

In `setup_ui`, replace the block that creates `self.projects_search`, `self.contributor_filter`, `self.refresh_btn`, and `top_layout` (lines 75–141) with:

```python
def setup_ui(self):
    self.filter_bar = FilterBar(
        filters=[
            TextFilterConfig(key="name", placeholder="🔍 Search for project by name"),
            ComboFilterConfig(key="who", placeholder="All contributors", dynamic=True),
            ComboFilterConfig(
                key="status",
                placeholder="All statuses",
                dynamic=False,
                items=[("Active", "active"), ("Archived", "archived")],
            ),
        ],
        refresh_callback=self.refresh,
        parent=self,
    )
    self.filter_bar.filters_changed.connect(self._apply_filters)
    # Create tree view with project files and model
    self.projects_model = QStandardItemModel()
    self.projects_tv = QTreeView()
    self.projects_tv.setModel(self.projects_model)
    self.projects_tv.setSortingEnabled(True)
    self.projects_tv.header().setSortIndicatorShown(True)
    self.projects_tv.header().setSectionsMovable(False)
    self.projects_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
    self.projects_tv.customContextMenuRequested.connect(self.show_context_menu)
    self.projects_tv.header().sortIndicatorChanged.connect(self.sort_projects)
    self.projects_model.setHorizontalHeaderLabels(
        ["Project Name", "Contributors", "Last activity", "Created at"]
    )
    avatar_delegate = ContributorAvatarsDelegate(self.projects_tv)
    self.projects_tv.setItemDelegateForColumn(1, avatar_delegate)
    self.projects_tv.doubleClicked.connect(self.select_project)
    layout = QVBoxLayout(self.projects_tv.viewport())
    layout.setContentsMargins(0, 0, 0, 0)
    self.empty_label = self.get_empty_placeholder()
    layout.addWidget(self.empty_label)
    # Create navigation buttons
    self.btn_previous = QPushButton("<")
    self.label_page_number = QLabel("Page 1/1")
    self.btn_next = QPushButton(">")
    self.btn_previous.clicked.connect(self.to_previous_page)
    self.btn_next.clicked.connect(self.to_next_page)
    # Organize widgets in layouts
    pagination_layout = QHBoxLayout()
    pagination_layout.addWidget(self.btn_previous)
    pagination_layout.addWidget(
        self.label_page_number, alignment=Qt.AlignmentFlag.AlignCenter
    )
    pagination_layout.addWidget(self.btn_next)
    layout = QVBoxLayout(self)
    layout.addWidget(self.filter_bar)
    layout.addWidget(self.projects_tv)
    layout.addLayout(pagination_layout)
    self.setLayout(layout)
```

Note: `self.refresh_btn` and `top_layout` are removed — the refresh button is now inside `FilterBar`. Also remove `QToolButton` and `QLineEdit` and `QComboBox` from the imports (handled in Step 1).

- [ ] **Step 3: Replace `filter_active`, `filter_projects`, contributor methods**

Replace the existing `filter_active` property and `filter_projects`, `get_projects_filtered_by_name`, `get_projects_filtered_by_contributor` methods with:

```python
@property
def filter_active(self):
    f = self.filter_bar.get_filters()
    return bool(f.get("name") or f.get("who") or f.get("status"))

def _apply_filters(self, filters: dict):
    if not self.filter_active:
        self.filtered_projects = self.tenant_projects
    else:
        name = filters.get("name", "").lower()
        who = filters.get("who", [])
        status = filters.get("status", [])
        self.filtered_projects = [
            p for p in self.tenant_projects
            if (not name or name in p["name"].lower())
            and (not who or any(c["id"] in who for c in p.get("contributors", [])))
            and (not status or p.get("status") in status)
        ]
    self.current_page = 1
    self.populate_projects()

def filter_projects(self):
    self._apply_filters(self.filter_bar.get_filters())
```

Also update `sort_projects` to call `self.filter_projects()` instead of `self.filter_projects()` / `self.populate_projects()` — it already does this, no change needed.

- [ ] **Step 4: Update `populate_contributors` to use `FilterBar`**

Replace:
```python
def populate_contributors(self):
    # ... builds sorted_users ...
    self.contributor_filter.blockSignals(True)
    self.contributor_filter.clear()
    for user in sorted_users:
        display_name = f"{user['given_name']} {user['family_name']}"
        if user["id"] == my_id:
            display_name += " (You)"
        user_image = self.avatar_cache.get_avatar_for_user(user)
        self.contributor_filter.addItem(QIcon(user_image), display_name, userData=user["id"])
    self.contributor_filter.setCurrentIndex(-1)
    self.contributor_filter.blockSignals(False)
```

with:

```python
def populate_contributors(self):
    all_contributors = {
        contributor["id"]: contributor
        for project in self.tenant_projects
        for contributor in project["contributors"]
    }
    my_info = get_user_info(self.communication)
    if my_info and my_info.get("sub") in all_contributors:
        my_id = my_info["sub"]
        my_user = [all_contributors.pop(my_id)]
    else:
        my_id = None
        my_user = []
    sorted_users = my_user + sorted(
        all_contributors.values(),
        key=lambda x: f"{x['given_name']} {x['family_name']}".lower(),
    )
    items = []
    for user in sorted_users:
        display_name = f"{user['given_name']} {user['family_name']}"
        if user["id"] == my_id:
            display_name += " (You)"
        avatar = self.avatar_cache.get_avatar_for_user(user)
        items.append((display_name, user["id"], avatar))
    self.filter_bar.set_combo_items("who", items)
```

- [ ] **Step 5: Update `update_avatar` to use `FilterBar`**

Replace:
```python
index = self.contributor_filter.findData(user_id)
if index != -1:
    self.contributor_filter.setItemIcon(index, QIcon(avatar))
```
with:
```python
self.filter_bar.update_combo_avatar("who", user_id, avatar)
```

- [ ] **Step 6: Remove `_on_contributor_filter_text_changed`**

Delete the `_on_contributor_filter_text_changed` method entirely — it was only needed because the old `QComboBox` was editable and needed text-change handling. `QgsCheckableComboBox` does not need this.

- [ ] **Step 7: Run tests**

```bash
docker compose run --rm qgis pytest -v tests/
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add rana_qgis_plugin/widgets/projects_browser.py
git commit -m "Connect FilterBar to ProjectsBrowser, add status filter"
```

**Manual testing path:** Open ProjectsBrowser → verify name search works → verify contributor multi-select works → verify status filter (Active/Archived) works → verify refresh button works → verify pagination still works correctly when filters are active.

---

### Task 3: Connect `FilterBar` to `ProcessesBrowser`

Add name, who, and status filters. Data arrives via `add_items()` / `update_job_state()` signals; all rows stay in the model and `setRowHidden()` is used for filtering.

**Files:**
- Modify: `rana_qgis_plugin/widgets/processes_browser.py`

- [ ] **Step 1: Update imports**

Add to imports:
```python
from qgis.PyQt.QtCore import QModelIndex, QSize, Qt, pyqtSignal, pyqtSlot
from rana_qgis_plugin.widgets.filter_bar import ComboFilterConfig, FilterBar, TextFilterConfig
```

- [ ] **Step 2: Add `FilterBar` to `setup_ui`**

In `setup_ui`, after creating `self.processes_model` and `self.processes_tv`, add the filter bar and insert it at the top of the layout:

```python
self.filter_bar = FilterBar(
    filters=[
        TextFilterConfig(key="name", placeholder="🔍 Search by name"),
        ComboFilterConfig(key="who", placeholder="All contributors", dynamic=True),
        ComboFilterConfig(
            key="status",
            placeholder="All statuses",
            dynamic=False,
            items=[
                ("Scheduled", "scheduled"),
                ("Pending", "pending"),
                ("Running", "running"),
                ("Completed", "completed"),
                ("Failed", "failed"),
                ("Cancelled", "cancelled"),
                ("Crashed", "crashed"),
                ("Paused", "paused"),
                ("Cancelling", "cancelling"),
            ],
        ),
    ],
    refresh_callback=lambda: None,  # ProcessesBrowser has no refresh; data arrives via signals
    parent=self,
)
self.filter_bar.filters_changed.connect(self._apply_filters)
layout = QVBoxLayout(self)
layout.addWidget(self.filter_bar)
layout.addWidget(self.processes_tv)
self.setLayout(layout)
```

Remove the old `layout = QVBoxLayout(self)` / `layout.addWidget(self.processes_tv)` / `self.setLayout(layout)` lines that are now replaced above.

- [ ] **Step 3: Add `_apply_filters` and `_reapply_filters`**

```python
def _apply_filters(self, filters: dict):
    name = filters.get("name", "").lower()
    who = filters.get("who", [])
    status = filters.get("status", [])
    root = self.processes_model.invisibleRootItem()
    for row in range(root.rowCount()):
        name_item = root.child(row, 0)
        job: JobData = name_item.data(Qt.ItemDataRole.UserRole)
        if job is None:
            continue
        visible = (
            (not name or name in job.name.lower())
            and (not who or job.user["id"] in who)
            and (not status or job.status in status)
        )
        self.processes_tv.setRowHidden(row, QModelIndex(), not visible)

def _reapply_filters(self):
    self._apply_filters(self.filter_bar.get_filters())
```

- [ ] **Step 4: Store `JobData` on name item and update `add_item`**

The filter needs `JobData` accessible from the name item's `UserRole`. Currently `name_item` has no `UserRole` data. Add it in `add_item`:

After the line `name_item = QStandardItem()`, add:
```python
name_item.setData(job, Qt.ItemDataRole.UserRole)
```

Also, after inserting the row at the end of `add_item`, call `_reapply_filters()` to apply any active filter to the new row, and populate the Who combo:

```python
self._reapply_filters()
self._repopulate_who_combo()
```

- [ ] **Step 5: Add `_repopulate_who_combo`**

The Who combo is populated dynamically from the jobs currently in the model:

```python
def _repopulate_who_combo(self):
    seen = {}
    root = self.processes_model.invisibleRootItem()
    for row in range(root.rowCount()):
        name_item = root.child(row, 0)
        job: JobData = name_item.data(Qt.ItemDataRole.UserRole)
        if job and job.user["id"] not in seen:
            seen[job.user["id"]] = job.user
    items = [
        (
            f"{u['given_name']} {u['family_name']}",
            u["id"],
            self.avatar_cache.get_avatar_for_user(u),
        )
        for u in seen.values()
    ]
    self.filter_bar.set_combo_items("who", items)
```

- [ ] **Step 6: Also update `JobData` on `update_state_for_job`**

When job state updates, refresh the stored `JobData` on the name item so filters remain accurate:

At the end of `update_state_for_job`, after updating the status item:
```python
name_item = self.processes_model.item(row, 0)
name_item.setData(job, Qt.ItemDataRole.UserRole)
self._reapply_filters()
```

- [ ] **Step 7: Clear combo on `update_project`**

In `update_project`, after `self.row_map.clear()`, reset the who combo:
```python
self.filter_bar.set_combo_items("who", [])
```

- [ ] **Step 8: Run tests**

```bash
docker compose run --rm qgis pytest -v tests/
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add rana_qgis_plugin/widgets/processes_browser.py
git commit -m "Connect FilterBar to ProcessesBrowser with name, who, status filters"
```

**Manual testing path:** Open ProcessesBrowser with an active project → verify name search filters job rows → verify who filter shows contributor avatars and filters correctly → verify status filter (e.g. "Completed") works → verify new jobs arriving via websocket still appear and respect active filters.

---

### Task 4: Connect `FilterBar` to `FilesBrowser`

Add name and type filters. The type combo is dynamically populated from `data_type` values of loaded files.

**Files:**
- Modify: `rana_qgis_plugin/widgets/files_browser.py`

- [ ] **Step 1: Update imports**

Add:
```python
from rana_qgis_plugin.widgets.filter_bar import ComboFilterConfig, FilterBar, TextFilterConfig
```

- [ ] **Step 2: Add `FilterBar` to `setup_ui`**

In `setup_ui`, add the filter bar and insert it at the top of the layout above the tree view:

```python
self.filter_bar = FilterBar(
    filters=[
        TextFilterConfig(key="name", placeholder="🔍 Search by filename"),
        ComboFilterConfig(key="type", placeholder="All types", dynamic=True),
    ],
    refresh_callback=self.refresh,  # or whichever method re-fetches files
    parent=self,
)
self.filter_bar.filters_changed.connect(self._apply_filters)
```

Add `self.filter_bar` to the layout before the tree view.

- [ ] **Step 3: Add `_apply_filters` and call it after `fetch_and_populate`**

```python
def _apply_filters(self, filters: dict):
    name = filters.get("name", "").lower()
    types = filters.get("type", [])
    root = self.files_model.invisibleRootItem()
    for row in range(root.rowCount()):
        name_item = root.child(row, 0)
        file_dict = name_item.data(Qt.ItemDataRole.UserRole)
        if file_dict is None:
            continue
        # Directories are never hidden by type filter; only hide by name
        is_dir = file_dict.get("type") == "directory"
        file_name = file_dict.get("name", "").lower()
        file_type = file_dict.get("data_type") or "unknown"
        visible = (not name or name in file_name) and (
            is_dir or not types or file_type in types
        )
        self.files_tv.setRowHidden(row, QModelIndex(), not visible)
```

At the end of `fetch_and_populate`, after populating the model, call:
```python
self._populate_type_combo()
self._apply_filters(self.filter_bar.get_filters())
```

- [ ] **Step 4: Add `_populate_type_combo`**

```python
def _populate_type_combo(self):
    seen = set()
    root = self.files_model.invisibleRootItem()
    for row in range(root.rowCount()):
        name_item = root.child(row, 0)
        file_dict = name_item.data(Qt.ItemDataRole.UserRole)
        if file_dict and file_dict.get("type") == "file":
            dt = file_dict.get("data_type") or "unknown"
            seen.add(dt)
    items = sorted(
        [(dt.capitalize() if dt != "unknown" else "Unknown", dt, None) for dt in seen],
        key=lambda x: x[0],
    )
    self.filter_bar.set_combo_items("type", items)
```

- [ ] **Step 5: Run tests**

```bash
docker compose run --rm qgis pytest -v tests/
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add rana_qgis_plugin/widgets/files_browser.py
git commit -m "Connect FilterBar to FilesBrowser with name and type filters"
```

**Manual testing path:** Open FilesBrowser → verify name search filters filenames → verify type combo is populated from loaded files → verify "Unknown" appears for files without `data_type` → verify navigating into a subdirectory resets and repopulates the type combo correctly.

---

### Task 5: Connect `FilterBar` to `PublicationsBrowser`

Add name and who filters. Data arrives via `add_items()` / `update_item()`.

**Files:**
- Modify: `rana_qgis_plugin/widgets/publications_browser.py`

- [ ] **Step 1: Update imports**

Add:
```python
from rana_qgis_plugin.widgets.filter_bar import ComboFilterConfig, FilterBar, TextFilterConfig
```

- [ ] **Step 2: Add `FilterBar` to `setup_ui`**

```python
self.filter_bar = FilterBar(
    filters=[
        TextFilterConfig(key="name", placeholder="🔍 Search by name"),
        ComboFilterConfig(key="who", placeholder="All contributors", dynamic=True),
    ],
    refresh_callback=lambda: None,  # PublicationsBrowser has no standalone refresh
    parent=self,
)
self.filter_bar.filters_changed.connect(self._apply_filters)
```

Add `self.filter_bar` to the layout above the tree view.

- [ ] **Step 3: Add `_apply_filters`**

```python
def _apply_filters(self, filters: dict):
    name = filters.get("name", "").lower()
    who = filters.get("who", [])
    root = self.publications_model.invisibleRootItem()
    for row in range(root.rowCount()):
        name_item = root.child(row, 0)
        pub_name = name_item.text().lower()
        who_item = root.child(row, 1)
        contributors = who_item.data(Qt.ItemDataRole.UserRole) or []
        visible = (
            (not name or name in pub_name)
            and (not who or any(c["id"] in who for c in contributors))
        )
        self.publications_tv.setRowHidden(row, QModelIndex(), not visible)
```

- [ ] **Step 4: Call `_apply_filters` and repopulate who combo after `add_items` and `update_item`**

Add a `_repopulate_who_combo` method:

```python
def _repopulate_who_combo(self):
    seen = {}
    root = self.publications_model.invisibleRootItem()
    for row in range(root.rowCount()):
        who_item = root.child(row, 1)
        contributors = who_item.data(Qt.ItemDataRole.UserRole) or []
        for c in contributors:
            if c["id"] not in seen:
                seen[c["id"]] = c
    items = [
        (c["name"], c["id"], c.get("avatar"))
        for c in seen.values()
    ]
    self.filter_bar.set_combo_items("who", items)
```

At the end of `add_items`, add:
```python
self._repopulate_who_combo()
self._apply_filters(self.filter_bar.get_filters())
```

At the end of `update_item`, add:
```python
self._reapply_filters()
```

Add `_reapply_filters`:
```python
def _reapply_filters(self):
    self._apply_filters(self.filter_bar.get_filters())
```

- [ ] **Step 5: Clear who combo on `update_project`**

In `update_project`, after clearing the model:
```python
self.filter_bar.set_combo_items("who", [])
```

- [ ] **Step 6: Run all tests**

```bash
docker compose run --rm qgis pytest -v tests/
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add rana_qgis_plugin/widgets/publications_browser.py
git commit -m "Connect FilterBar to PublicationsBrowser with name and who filters"
```

**Manual testing path:** Open PublicationsBrowser → verify name search filters publications → verify who combo shows contributor avatars → verify filtering by contributor works → verify new publications arriving via websocket respect active filters.
