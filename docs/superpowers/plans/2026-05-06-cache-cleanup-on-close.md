# Cache Cleanup on Close — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in setting to automatically empty the Rana cache directory when QGIS exits, with a one-time modal prompt for users who haven't set the preference yet.

**Architecture:** A new `utils/cache.py` module holds the cleanup logic. Two new accessor functions are added to `utils/settings.py`. The main plugin class connects to `QgsApplication.aboutToQuit` in `initGui()` and disconnects in `unload()`, ensuring cleanup only runs on real QGIS exit (not plugin reload). A checkbox is added to the settings dialog in the File Storage section.

**Tech Stack:** Python, PyQt5/PyQt6 (via qgis.PyQt), pathlib, shutil, QgsSettings, QgsApplication

---

### Task 1: Add settings accessors for cleanup preference

**Files:**
- Modify: `rana_qgis_plugin/utils/settings.py`
- Test: `tests/test_utils_settings.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_utils_settings.py`:

```python
from rana_qgis_plugin.utils.settings import (
    cleanup_cache_on_close,
    set_cleanup_cache_on_close,
)


@pytest.mark.parametrize(
    "stored_value,expected",
    [
        (None, False),       # key absent → default False
        ("true", True),
        ("false", False),
    ],
    ids=["absent", "true", "false"],
)
def test_cleanup_cache_on_close(stored_value, expected):
    with patch("rana_qgis_plugin.utils.settings.QgsSettings") as mock_settings:
        mock_instance = MagicMock()
        mock_settings.return_value = mock_instance
        mock_instance.value.return_value = stored_value
        result = cleanup_cache_on_close()
        assert result == expected
        mock_instance.value.assert_called_with(
            "Rana/cleanup_cache_on_close", False, type=bool
        )


def test_set_cleanup_cache_on_close():
    with patch("rana_qgis_plugin.utils.settings.QgsSettings") as mock_settings:
        mock_instance = MagicMock()
        mock_settings.return_value = mock_instance
        set_cleanup_cache_on_close(True)
        mock_instance.setValue.assert_called_once_with(
            "Rana/cleanup_cache_on_close", True
        )


def test_cleanup_cache_on_close_key_absent_detection():
    """Key absent (None from QgsSettings.value without default) means not yet set."""
    with patch("rana_qgis_plugin.utils.settings.QgsSettings") as mock_settings:
        mock_instance = MagicMock()
        mock_settings.return_value = mock_instance
        mock_instance.value.return_value = None
        # Simulate absence check used in initGui
        result = mock_instance.value("Rana/cleanup_cache_on_close")
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
docker compose run --rm qgis pytest -v tests/test_utils_settings.py::test_cleanup_cache_on_close tests/test_utils_settings.py::test_set_cleanup_cache_on_close
```

Expected: `ImportError` or `FAILED` — functions don't exist yet.

- [ ] **Step 3: Add the two functions to `utils/settings.py`**

Add after the `set_rana_cache_dir` function (after line 114):

```python
def cleanup_cache_on_close() -> bool:
    return QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/cleanup_cache_on_close", False, type=bool)


def set_cleanup_cache_on_close(value: bool) -> None:
    QgsSettings().setValue(f"{RANA_SETTINGS_ENTRY}/cleanup_cache_on_close", value)
```

- [ ] **Step 4: Run tests to verify they pass**

```
docker compose run --rm qgis pytest -v tests/test_utils_settings.py::test_cleanup_cache_on_close tests/test_utils_settings.py::test_set_cleanup_cache_on_close
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add rana_qgis_plugin/utils/settings.py tests/test_utils_settings.py
git commit -m "Add cleanup_cache_on_close settings accessors"
```

---

### Task 2: Create `utils/cache.py` with cleanup function

**Files:**
- Create: `rana_qgis_plugin/utils/cache.py`
- Create: `tests/test_utils_cache.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_utils_cache.py`:

```python
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rana_qgis_plugin.utils.cache import cleanup_cache


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """A temporary cache directory with some files and subdirs."""
    (tmp_path / "file1.txt").write_text("data")
    (tmp_path / "file2.txt").write_text("data")
    subdir = tmp_path / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested")
    return tmp_path


def _make_communication():
    comm = MagicMock()
    return comm


def test_cleanup_cache_removes_contents(tmp_cache_dir):
    """All files and subdirs inside the cache dir are removed."""
    communication = _make_communication()
    with patch(
        "rana_qgis_plugin.utils.cache.rana_cache_dir",
        return_value=str(tmp_cache_dir),
    ):
        cleanup_cache(communication)

    remaining = list(tmp_cache_dir.iterdir())
    assert remaining == [], f"Expected empty dir, got: {remaining}"
    communication.log_warn.assert_not_called()


def test_cleanup_cache_keeps_folder(tmp_cache_dir):
    """The cache dir itself is not removed."""
    communication = _make_communication()
    with patch(
        "rana_qgis_plugin.utils.cache.rana_cache_dir",
        return_value=str(tmp_cache_dir),
    ):
        cleanup_cache(communication)

    assert tmp_cache_dir.exists()


def test_cleanup_cache_nonexistent_dir():
    """If cache dir does not exist, no error is raised."""
    communication = _make_communication()
    with patch(
        "rana_qgis_plugin.utils.cache.rana_cache_dir",
        return_value="/nonexistent/path/rana_cache_test_xyz",
    ):
        cleanup_cache(communication)  # must not raise

    communication.log_warn.assert_not_called()


def test_cleanup_cache_logs_warn_on_failure(tmp_cache_dir):
    """If a deletion fails, log_warn is called and no exception is raised."""
    communication = _make_communication()

    def failing_rmtree(path, *args, **kwargs):
        raise OSError("Permission denied")

    with patch(
        "rana_qgis_plugin.utils.cache.rana_cache_dir",
        return_value=str(tmp_cache_dir),
    ), patch("rana_qgis_plugin.utils.cache.shutil.rmtree", side_effect=failing_rmtree):
        cleanup_cache(communication)  # must not raise

    assert communication.log_warn.called


def test_cleanup_cache_empty_dir(tmp_path):
    """An already-empty cache dir is handled without error."""
    communication = _make_communication()
    with patch(
        "rana_qgis_plugin.utils.cache.rana_cache_dir",
        return_value=str(tmp_path),
    ):
        cleanup_cache(communication)

    communication.log_warn.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```
docker compose run --rm qgis pytest -v tests/test_utils_cache.py
```

Expected: `ImportError` — module doesn't exist yet.

- [ ] **Step 3: Create `rana_qgis_plugin/utils/cache.py`**

```python
import shutil
from pathlib import Path

from rana_qgis_plugin.utils.settings import rana_cache_dir


def cleanup_cache(communication) -> None:
    """Remove all contents of the Rana cache directory, keeping the folder itself.

    Failures are logged via communication.log_warn and never raised.
    """
    cache_path = rana_cache_dir()
    if not cache_path:
        return
    cache_dir = Path(cache_path)
    if not cache_dir.exists():
        return
    for item in cache_dir.iterdir():
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except Exception as exc:
            communication.log_warn(f"Cache cleanup failed for {item}: {exc}")
```

- [ ] **Step 4: Run tests to verify they pass**

```
docker compose run --rm qgis pytest -v tests/test_utils_cache.py
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add rana_qgis_plugin/utils/cache.py tests/test_utils_cache.py
git commit -m "Add cache cleanup utility"
```

---

### Task 3: Wire cleanup into the main plugin class

**Files:**
- Modify: `rana_qgis_plugin/rana_qgis_plugin.py`

No unit tests for this task — the wiring involves QGIS signals that require integration testing. Manual test path is described at the end of this task.

- [ ] **Step 1: Add imports to `rana_qgis_plugin.py`**

At the top of the file, add to the existing `from rana_qgis_plugin.utils.settings import (...)` block:

```python
from rana_qgis_plugin.utils.cache import cleanup_cache
from rana_qgis_plugin.utils.settings import (
    cleanup_cache_on_close,
    set_cleanup_cache_on_close,
    # ... existing imports
)
```

Also add `QgsSettings` to the `qgis.core` import if not already present:

```python
from qgis.core import QgsApplication, QgsSettings
```

- [ ] **Step 2: Add `_on_qgis_closing` slot to `RanaQgisPlugin`**

Add this method to the `RanaQgisPlugin` class (e.g., just before `unload`):

```python
def _on_qgis_closing(self) -> None:
    """Slot called when QGIS is about to quit. Cleans up cache if enabled."""
    if cleanup_cache_on_close():
        cleanup_cache(self.communication)
```

- [ ] **Step 3: Update `initGui` to connect signal and show one-time prompt**

Replace the existing `initGui` method:

```python
def initGui(self):
    """Create the (initial) menu entries and toolbar icons inside the QGIS GUI."""
    if get_use_plugin_excepthook():
        install_exception_hook()
    self.add_rana_menu(False)
    self.toolbar.addAction(self.action)
    self.provider = RanaQgisPluginProvider()
    QgsApplication.processingRegistry().addProvider(self.provider)

    # Connect cache cleanup to QGIS exit signal
    QgsApplication.instance().aboutToQuit.connect(self._on_qgis_closing)

    # One-time prompt if preference has never been set
    if QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/cleanup_cache_on_close") is None:
        result = UICommunication.ask(
            self.iface.mainWindow(),
            PLUGIN_NAME,
            "Do you want Rana to automatically empty the cache folder when QGIS closes?",
        )
        set_cleanup_cache_on_close(result)
```

Also add `RANA_SETTINGS_ENTRY` to the constant imports at the top of the file:

```python
from rana_qgis_plugin.constant import PLUGIN_NAME, RANA_SETTINGS_ENTRY
```

- [ ] **Step 4: Update `unload` to disconnect the signal**

Add the disconnect at the start of `unload()`:

```python
def unload(self):
    """Removes the plugin menu item and icon from QGIS GUI."""
    try:
        QgsApplication.instance().aboutToQuit.disconnect(self._on_qgis_closing)
    except RuntimeError:
        pass  # Already disconnected or never connected
    QgsApplication.processingRegistry().removeProvider(self.provider)
    # ... rest of existing unload code unchanged
```

- [ ] **Step 5: Run the full test suite to check for regressions**

```
docker compose run --rm qgis pytest -v tests/
```

Expected: all existing tests pass, no new failures.

- [ ] **Step 6: Commit**

```bash
git add rana_qgis_plugin/rana_qgis_plugin.py
git commit -m "Connect cache cleanup to QGIS aboutToQuit signal"
```

**Manual test path:**
1. Install/reload the plugin — a dialog should appear asking about cache cleanup (first time only).
2. Answer "No" → `Rana/cleanup_cache_on_close` should be `false` in QgsSettings. Dialog should not appear again on next QGIS start.
3. Enable cleanup via Settings dialog. Close QGIS. Cache dir contents should be gone; the folder itself should still exist.
4. Reload the plugin via Plugin Manager (without closing QGIS) — cache dir should NOT be emptied.

---

### Task 4: Add checkbox to settings dialog

**Files:**
- Modify: `rana_qgis_plugin/widgets/settings_dialog.py`

- [ ] **Step 1: Add imports to `settings_dialog.py`**

Add `QCheckBox` to the `qgis.PyQt.QtWidgets` import block:

```python
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)
```

Add to the `utils.settings` import block:

```python
from rana_qgis_plugin.utils.settings import (
    base_url,
    cleanup_cache_on_close,
    get_advanced_settings,
    hcc_working_dir,
    rana_cache_dir,
    set_base_url,
    set_cleanup_cache_on_close,
    set_cognito_client_id,
    set_cognito_client_id_native,
    set_hcc_working_dir,
    set_rana_cache_dir,
)
```

- [ ] **Step 2: Add checkbox widget to `files_group` in `__init__`**

The current `files_group` block ends at line 75. After the browse button wiring (after the `if rana_cache_dir(return_default=False) is None:` block), add:

```python
        self.cleanup_cache_cb = QCheckBox("Empty cache directory on closing QGIS", files_group)
        self.cleanup_cache_cb.setChecked(cleanup_cache_on_close())
        files_group.layout().addWidget(self.cleanup_cache_cb, 1, 0, 1, 3)
```

This places the checkbox on the second row (`row=1`), spanning all 3 columns.

- [ ] **Step 3: Save checkbox value in `accept`**

In the `accept` method, add before `return super().accept()`:

```python
        set_cleanup_cache_on_close(self.cleanup_cache_cb.isChecked())
```

- [ ] **Step 4: Run the full test suite**

```
docker compose run --rm qgis pytest -v tests/
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add rana_qgis_plugin/widgets/settings_dialog.py
git commit -m "Add cleanup cache checkbox to settings dialog"
```

**Manual test path:**
1. Open Settings dialog. Verify "Empty cache directory on closing QGIS" checkbox appears in the File Storage section.
2. Toggle it and click OK. Re-open Settings — verify the value persisted.
