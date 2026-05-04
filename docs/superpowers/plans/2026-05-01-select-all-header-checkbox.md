# Select-All Header Checkbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a tri-state select-all checkbox to the header of column 0 in the files treeview that selects/deselects all file rows when clicked and reflects the current selection state.

**Architecture:** A `CheckableHeaderView` subclass of `QHeaderView` is added to `utils_view.py`. It paints a native Qt checkbox in section 0 and emits a signal when clicked. `FilesBrowser` wires the signal to check/uncheck all rows, and extends `_update_batch_buttons` to sync the header checkbox state after any row change.

**Tech Stack:** PyQt5/qgis.PyQt, `QHeaderView`, `QStyleOptionButton`, `QStyle.drawControl`

---

### Task 1: Add `CheckableHeaderView` to `utils_view.py`

**Files:**
- Modify: `rana_qgis_plugin/widgets/utils_view.py`
- Test: `tests/test_checkable_header_view.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_checkable_header_view.py`:

```python
"""Tests for CheckableHeaderView."""

import pytest
from qgis.PyQt.QtCore import Qt

from rana_qgis_plugin.widgets.utils_view import CheckableHeaderView


@pytest.fixture
def header(qtbot):
    h = CheckableHeaderView(Qt.Orientation.Horizontal)
    h.setMinimumSectionSize(10)
    h.resize(200, 30)
    qtbot.addWidget(h)
    return h


def test_initial_check_state_is_unchecked(header):
    assert header.check_state() == Qt.CheckState.Unchecked


def test_set_check_state_checked(header):
    header.set_check_state(Qt.CheckState.Checked)
    assert header.check_state() == Qt.CheckState.Checked


def test_set_check_state_partial(header):
    header.set_check_state(Qt.CheckState.PartiallyChecked)
    assert header.check_state() == Qt.CheckState.PartiallyChecked


def test_set_check_state_unchecked(header):
    header.set_check_state(Qt.CheckState.Checked)
    header.set_check_state(Qt.CheckState.Unchecked)
    assert header.check_state() == Qt.CheckState.Unchecked
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose run --rm qgis pytest -v tests/test_checkable_header_view.py
```

Expected: ImportError or AttributeError — `CheckableHeaderView` does not exist yet.

- [ ] **Step 3: Implement `CheckableHeaderView` in `utils_view.py`**

At the top of `rana_qgis_plugin/widgets/utils_view.py`, change the imports to:

```python
from qgis.PyQt.QtCore import Qt, pyqtSignal, QRect
from qgis.PyQt.QtWidgets import QHeaderView, QStyle, QStyleOptionButton, QTreeView
```

Then append this class at the end of the file:

```python
class CheckableHeaderView(QHeaderView):
    """
    A QHeaderView that renders a tri-state checkbox in section 0.
    Emits check_state_changed(Qt.CheckState) when the user clicks the checkbox.
    Use set_check_state() to update the visual state from outside.
    """

    check_state_changed = pyqtSignal(object)  # Qt.CheckState

    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self._check_state = Qt.CheckState.Unchecked
        self.setSectionsClickable(True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_state(self) -> "Qt.CheckState":
        return self._check_state

    def set_check_state(self, state: "Qt.CheckState"):
        """Update the visual checkbox state without emitting a signal."""
        if self._check_state != state:
            self._check_state = state
            self.viewport().update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintSection(self, painter, rect, logical_index):
        super().paintSection(painter, rect, logical_index)
        if logical_index != 0:
            return
        opt = QStyleOptionButton()
        opt.rect = self._checkbox_rect(rect)
        if self._check_state == Qt.CheckState.Checked:
            opt.state = QStyle.State_On | QStyle.State_Enabled
        elif self._check_state == Qt.CheckState.PartiallyChecked:
            opt.state = QStyle.State_NoChange | QStyle.State_Enabled
        else:
            opt.state = QStyle.State_Off | QStyle.State_Enabled
        self.style().drawControl(QStyle.ControlElement.CE_CheckBox, opt, painter)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        logical = self.logicalIndexAt(event.pos())
        if logical == 0:
            section_rect = QRect(
                self.sectionViewportPosition(0), 0, self.sectionSize(0), self.height()
            )
            if self._checkbox_rect(section_rect).contains(event.pos()):
                new_state = (
                    Qt.CheckState.Unchecked
                    if self._check_state == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                self._check_state = new_state
                self.viewport().update()
                self.check_state_changed.emit(new_state)
                return
        super().mousePressEvent(event)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _checkbox_rect(self, section_rect):
        """Return a QRect centered in section_rect sized to the checkbox indicator."""
        opt = QStyleOptionButton()
        cb_size = self.style().subElementRect(
            QStyle.SubElement.SE_CheckBoxIndicator, opt, self
        ).size()
        x = section_rect.x() + (section_rect.width() - cb_size.width()) // 2
        y = section_rect.y() + (section_rect.height() - cb_size.height()) // 2
        return QRect(x, y, cb_size.width(), cb_size.height())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
docker compose run --rm qgis pytest -v tests/test_checkable_header_view.py
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rana_qgis_plugin/widgets/utils_view.py tests/test_checkable_header_view.py
git commit -m "Add CheckableHeaderView with tri-state checkbox in section 0"
```

---

### Task 2: Wire `CheckableHeaderView` into `FilesBrowser`

**Files:**
- Modify: `rana_qgis_plugin/widgets/files_browser.py`
- Test: `tests/test_files_browser_select_all.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_files_browser_select_all.py`:

```python
"""Tests for select-all header checkbox in FilesBrowser."""

from unittest.mock import MagicMock, patch

import pytest
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItem

from rana_qgis_plugin.widgets.files_browser import FilesBrowser


def make_files_browser(qtbot):
    project = MagicMock()
    project.id = "test-project-id"
    communication = MagicMock()

    with patch(
        "rana_qgis_plugin.widgets.files_browser.get_tenant_project_files",
        return_value={"results": [], "next": None},
    ):
        browser = FilesBrowser(communication, project)
        qtbot.addWidget(browser)
        browser.select_btn.setChecked(True)
        browser.toggle_select_mode(True)
    return browser


def _add_file_row(browser, file_id="f1", name="file.txt"):
    checkbox_item = QStandardItem()
    checkbox_item.setCheckable(True)
    checkbox_item.setCheckState(Qt.CheckState.Unchecked)
    checkbox_item.setFlags(
        Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
    )
    name_item = QStandardItem(name)
    name_item.setData({"id": file_id, "name": name, "type": "file"}, Qt.ItemDataRole.UserRole)
    browser.files_model.appendRow([checkbox_item, name_item])
    return checkbox_item


def test_header_checkbox_starts_unchecked(qtbot):
    browser = make_files_browser(qtbot)
    assert browser.files_tv.header().check_state() == Qt.CheckState.Unchecked


def test_clicking_header_checks_all_rows(qtbot):
    browser = make_files_browser(qtbot)
    cb1 = _add_file_row(browser, "f1", "a.txt")
    cb2 = _add_file_row(browser, "f2", "b.txt")

    browser._on_header_check_state_changed(Qt.CheckState.Checked)

    assert cb1.checkState() == Qt.CheckState.Checked
    assert cb2.checkState() == Qt.CheckState.Checked


def test_clicking_header_unchecks_all_rows(qtbot):
    browser = make_files_browser(qtbot)
    cb1 = _add_file_row(browser, "f1", "a.txt")
    cb1.setCheckState(Qt.CheckState.Checked)

    browser._on_header_check_state_changed(Qt.CheckState.Unchecked)

    assert cb1.checkState() == Qt.CheckState.Unchecked


def test_all_checked_syncs_header_to_checked(qtbot):
    browser = make_files_browser(qtbot)
    cb1 = _add_file_row(browser, "f1", "a.txt")
    cb2 = _add_file_row(browser, "f2", "b.txt")
    cb1.setCheckState(Qt.CheckState.Checked)
    cb2.setCheckState(Qt.CheckState.Checked)

    browser._sync_header_checkbox()

    assert browser.files_tv.header().check_state() == Qt.CheckState.Checked


def test_some_checked_syncs_header_to_partial(qtbot):
    browser = make_files_browser(qtbot)
    cb1 = _add_file_row(browser, "f1", "a.txt")
    _add_file_row(browser, "f2", "b.txt")
    cb1.setCheckState(Qt.CheckState.Checked)

    browser._sync_header_checkbox()

    assert browser.files_tv.header().check_state() == Qt.CheckState.PartiallyChecked


def test_none_checked_syncs_header_to_unchecked(qtbot):
    browser = make_files_browser(qtbot)
    _add_file_row(browser, "f1", "a.txt")

    browser._sync_header_checkbox()

    assert browser.files_tv.header().check_state() == Qt.CheckState.Unchecked
```

- [ ] **Step 2: Run test to verify it fails**

```bash
docker compose run --rm qgis pytest -v tests/test_files_browser_select_all.py
```

Expected: AttributeError — `_on_header_check_state_changed` and `_sync_header_checkbox` do not exist yet.

- [ ] **Step 3: Update import in `files_browser.py`**

Change the `utils_view` import line from:

```python
from rana_qgis_plugin.widgets.utils_view import ContentAwareTreeView
```

to:

```python
from rana_qgis_plugin.widgets.utils_view import CheckableHeaderView, ContentAwareTreeView
```

- [ ] **Step 4: Replace header in `setup_ui`**

In `setup_ui`, find these lines (around line 125):

```python
        self.files_tv = ContentAwareTreeView()
        self.files_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
```

Replace with:

```python
        self.files_tv = ContentAwareTreeView()
        self.files_tv.setHeader(CheckableHeaderView(Qt.Orientation.Horizontal, self.files_tv))
        self.files_tv.header().check_state_changed.connect(self._on_header_check_state_changed)
        self.files_tv.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
```

- [ ] **Step 5: Add `_on_header_check_state_changed` and `_sync_header_checkbox` methods**

After the `_update_batch_buttons` method (after line 276), add:

```python
    def _on_header_check_state_changed(self, state: Qt.CheckState):
        """Called when the user clicks the header checkbox. Check or uncheck all file rows."""
        self.files_model.blockSignals(True)
        try:
            for row in range(self.files_model.rowCount()):
                checkbox_item = self.files_model.item(row, 0)
                if checkbox_item and checkbox_item.isCheckable():
                    checkbox_item.setCheckState(state)
        finally:
            self.files_model.blockSignals(False)
        has_checked = state == Qt.CheckState.Checked
        self.btn_download_selected.setEnabled(has_checked)
        self.btn_delete_selected.setEnabled(has_checked)
        self.files_tv.header().set_check_state(state)

    def _sync_header_checkbox(self):
        """Update header checkbox to reflect current row check states."""
        total = 0
        checked = 0
        for row in range(self.files_model.rowCount()):
            checkbox_item = self.files_model.item(row, 0)
            if checkbox_item and checkbox_item.isCheckable():
                total += 1
                if checkbox_item.checkState() == Qt.CheckState.Checked:
                    checked += 1
        if total == 0 or checked == 0:
            state = Qt.CheckState.Unchecked
        elif checked == total:
            state = Qt.CheckState.Checked
        else:
            state = Qt.CheckState.PartiallyChecked
        self.files_tv.header().set_check_state(state)
```

- [ ] **Step 6: Call `_sync_header_checkbox` from `_update_batch_buttons`**

Find `_update_batch_buttons` (around line 269) and replace its body:

```python
    def _update_batch_buttons(self, item: QStandardItem):
        """Enable/disable batch buttons based on checked count. Called on itemChanged."""
        if item.column() != 0:
            return
        has_checked = len(self._get_checked_files()) > 0
        self.btn_download_selected.setEnabled(has_checked)
        self.btn_delete_selected.setEnabled(has_checked)
        self._sync_header_checkbox()
```

- [ ] **Step 7: Reset header checkbox when exiting select mode**

In `toggle_select_mode`, find:

```python
        if not checked:
            self._clear_all_checkboxes()
```

Replace with:

```python
        if not checked:
            self._clear_all_checkboxes()
            self.files_tv.header().set_check_state(Qt.CheckState.Unchecked)
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
docker compose run --rm qgis pytest -v tests/test_files_browser_select_all.py
```

Expected: 6 tests PASS.

- [ ] **Step 9: Run full test suite**

```bash
docker compose run --rm qgis pytest -v tests
```

Expected: all tests PASS.

- [ ] **Step 10: Commit**

```bash
git add rana_qgis_plugin/widgets/files_browser.py tests/test_files_browser_select_all.py
git commit -m "Wire CheckableHeaderView into FilesBrowser for select-all behavior"
```

---

## Manual Testing Checklist

UI paths to verify manually in QGIS:

1. Open the Files Browser and click **Select** — header section 0 shows an unchecked checkbox
2. Click the header checkbox → all file rows become checked; header shows checked
3. Uncheck one row → header shows partially checked (indeterminate)
4. Uncheck all rows manually → header shows unchecked
5. Check all rows manually → header shows checked
6. With some rows checked, click header checkbox → all rows become checked
7. Click header checkbox again → all rows become unchecked
8. Exit select mode → re-enter → header checkbox resets to unchecked
9. Directory rows are unaffected by select-all
