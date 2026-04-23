# HCC URL Override Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add support for overriding the 3Di API URL via QgsSettings, with a read-only Advanced section in Settings Dialog.

**Architecture:** Add two new functions to `settings.py` for retrieving hcc_url override and collecting advanced settings. Modify `get_threedi_api()` in `generic.py` to check for the override. Update Settings Dialog to display advanced settings when configured.

**Tech Stack:** Python 3.7+, PyQt5, QGIS API, QgsSettings

---

## File Structure

**Files to modify:**
- `rana_qgis_plugin/utils/settings.py` — Add two new functions
- `rana_qgis_plugin/utils/generic.py` — Modify get_threedi_api() to check override
- `rana_qgis_plugin/widgets/settings_dialog.py` — Add Advanced section display
- `tests/test_settings.py` — Add unit tests for new functions
- `tests/test_generic.py` — Add unit tests for override behavior

---

## Tasks

### Task 1: Add get_hcc_url_override() function to settings.py

**Files:**
- Modify: `rana_qgis_plugin/utils/settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write the failing test for get_hcc_url_override()**

Open `tests/test_settings.py` and add:

```python
def test_get_hcc_url_override_not_set(qgs_settings_mock):
    """When hcc_url is not set, returns None"""
    result = get_hcc_url_override()
    assert result is None


def test_get_hcc_url_override_when_set(qgs_settings_mock):
    """When hcc_url is set, returns the value"""
    qgs_settings_mock.value.return_value = "https://dev-3di-api.example.com"
    result = get_hcc_url_override()
    assert result == "https://dev-3di-api.example.com"
    qgs_settings_mock.value.assert_called_with("Rana/hcc_url")


def test_get_hcc_url_override_empty_string(qgs_settings_mock):
    """When hcc_url is set to empty string, returns empty string"""
    qgs_settings_mock.value.return_value = ""
    result = get_hcc_url_override()
    assert result == ""
```

Assume a fixture `qgs_settings_mock` exists (if not, create it or use monkeypatch).

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/margriet/src/rana-qgis-plugin
docker compose run --rm qgis pytest tests/test_settings.py::test_get_hcc_url_override_not_set -v
```

Expected output: FAILED (function does not exist)

- [ ] **Step 3: Implement get_hcc_url_override() in settings.py**

Open `rana_qgis_plugin/utils/settings.py` and add this function (place it after other getter functions like `get_tenant_id()`):

```python
def get_hcc_url_override() -> Optional[str]:
    """
    Get the 3Di API URL override from QgsSettings.
    
    Returns:
        The hcc_url value if set in QgsSettings, None otherwise.
    """
    return QgsSettings().value("Rana/hcc_url")
```

Make sure `Optional` is imported from `typing` at the top of the file.

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose run --rm qgis pytest tests/test_settings.py::test_get_hcc_url_override_not_set tests/test_settings.py::test_get_hcc_url_override_when_set tests/test_settings.py::test_get_hcc_url_override_empty_string -v
```

Expected: PASSED (all three tests)

- [ ] **Step 5: Commit**

```bash
cd /home/margriet/src/rana-qgis-plugin
git add rana_qgis_plugin/utils/settings.py tests/test_settings.py
git commit -m "Add get_hcc_url_override() function to retrieve hcc_url from QgsSettings"
```

---

### Task 2: Add get_advanced_settings() function to settings.py

**Files:**
- Modify: `rana_qgis_plugin/utils/settings.py`
- Test: `tests/test_settings.py`

- [ ] **Step 1: Write failing tests for get_advanced_settings()**

Add to `tests/test_settings.py`:

```python
def test_get_advanced_settings_empty_when_none_set(qgs_settings_mock):
    """When no advanced settings are set, returns empty dict"""
    qgs_settings_mock.value.return_value = None
    result = get_advanced_settings()
    assert result == {}


def test_get_advanced_settings_includes_hcc_url_when_set(qgs_settings_mock):
    """When hcc_url is set, includes it in returned dict"""
    def mock_value(key):
        if key == "Rana/hcc_url":
            return "https://dev-3di-api.example.com"
        return None
    
    qgs_settings_mock.value.side_effect = mock_value
    result = get_advanced_settings()
    assert "hcc_url" in result
    assert result["hcc_url"] == "https://dev-3di-api.example.com"


def test_get_advanced_settings_includes_use_plugin_excepthook_when_set(qgs_settings_mock):
    """When use_plugin_excepthook is set, includes it in returned dict"""
    def mock_value(key):
        if key == "Rana/use_plugin_excepthook":
            return "true"
        return None
    
    qgs_settings_mock.value.side_effect = mock_value
    result = get_advanced_settings()
    assert "use_plugin_excepthook" in result
    assert result["use_plugin_excepthook"] == "true"


def test_get_advanced_settings_includes_both_when_set(qgs_settings_mock):
    """When both are set, includes both in returned dict"""
    def mock_value(key):
        if key == "Rana/hcc_url":
            return "https://dev-3di-api.example.com"
        elif key == "Rana/use_plugin_excepthook":
            return "true"
        return None
    
    qgs_settings_mock.value.side_effect = mock_value
    result = get_advanced_settings()
    assert len(result) == 2
    assert result["hcc_url"] == "https://dev-3di-api.example.com"
    assert result["use_plugin_excepthook"] == "true"


def test_get_advanced_settings_excludes_empty_values(qgs_settings_mock):
    """When value is empty string, excludes it from returned dict"""
    def mock_value(key):
        if key == "Rana/hcc_url":
            return ""
        return None
    
    qgs_settings_mock.value.side_effect = mock_value
    result = get_advanced_settings()
    assert "hcc_url" not in result
    assert result == {}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose run --rm qgis pytest tests/test_settings.py::test_get_advanced_settings_empty_when_none_set -v
```

Expected: FAILED (function does not exist)

- [ ] **Step 3: Implement get_advanced_settings() in settings.py**

Open `rana_qgis_plugin/utils/settings.py` and add this function (after `get_hcc_url_override()`):

```python
def get_advanced_settings() -> dict:
    """
    Get all configured advanced settings that have values.
    
    Returns:
        Dictionary of advanced setting key-value pairs.
        Only includes settings that have non-empty values.
        Example: {"hcc_url": "https://...", "use_plugin_excepthook": "true"}
    """
    advanced_settings = {}
    
    # Check hcc_url
    hcc_url = QgsSettings().value("Rana/hcc_url")
    if hcc_url:
        advanced_settings["hcc_url"] = hcc_url
    
    # Check use_plugin_excepthook
    use_plugin_excepthook = QgsSettings().value("Rana/use_plugin_excepthook")
    if use_plugin_excepthook:
        advanced_settings["use_plugin_excepthook"] = use_plugin_excepthook
    
    return advanced_settings
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose run --rm qgis pytest tests/test_settings.py::test_get_advanced_settings_empty_when_none_set tests/test_settings.py::test_get_advanced_settings_includes_hcc_url_when_set tests/test_settings.py::test_get_advanced_settings_includes_use_plugin_excepthook_when_set tests/test_settings.py::test_get_advanced_settings_includes_both_when_set tests/test_settings.py::test_get_advanced_settings_excludes_empty_values -v
```

Expected: PASSED (all five tests)

- [ ] **Step 5: Commit**

```bash
git add rana_qgis_plugin/utils/settings.py tests/test_settings.py
git commit -m "Add get_advanced_settings() to collect configured advanced settings"
```

---

### Task 3: Modify get_threedi_api() to use hcc_url override

**Files:**
- Modify: `rana_qgis_plugin/utils/generic.py`
- Test: `tests/test_generic.py`

- [ ] **Step 1: Write failing tests for get_threedi_api() override behavior**

Open `tests/test_generic.py` and add these tests. Assume fixtures for mocking exist (`mock_3di_auth`, `mock_api_client`, etc.):

```python
def test_get_threedi_api_uses_override_when_set(mock_3di_auth, mock_api_client, mocker):
    """When hcc_url override is set, uses that URL"""
    # Mock the override function to return a custom URL
    mocker.patch(
        "rana_qgis_plugin.utils.generic.get_hcc_url_override",
        return_value="https://dev-3di-api.example.com"
    )
    # Mock frontend settings
    mocker.patch(
        "rana_qgis_plugin.utils.generic.get_frontend_settings",
        return_value={"hcc_url": "https://default-3di-api.example.com"}
    )
    
    result = get_threedi_api()
    
    # Verify the override URL was used (not the frontend settings URL)
    mock_api_client.assert_called_with("token", "https://dev-3di-api.example.com")
    assert result is not None


def test_get_threedi_api_uses_frontend_settings_when_no_override(mock_3di_auth, mock_api_client, mocker):
    """When hcc_url override is None, uses frontend_settings value"""
    # Mock the override function to return None
    mocker.patch(
        "rana_qgis_plugin.utils.generic.get_hcc_url_override",
        return_value=None
    )
    # Mock frontend settings
    mocker.patch(
        "rana_qgis_plugin.utils.generic.get_frontend_settings",
        return_value={"hcc_url": "https://default-3di-api.example.com"}
    )
    
    result = get_threedi_api()
    
    # Verify the frontend settings URL was used
    mock_api_client.assert_called_with("token", "https://default-3di-api.example.com")
    assert result is not None


def test_get_threedi_api_uses_frontend_settings_when_override_empty(mock_3di_auth, mock_api_client, mocker):
    """When hcc_url override is empty string, falls back to frontend_settings"""
    # Mock the override function to return empty string
    mocker.patch(
        "rana_qgis_plugin.utils.generic.get_hcc_url_override",
        return_value=""
    )
    # Mock frontend settings
    mocker.patch(
        "rana_qgis_plugin.utils.generic.get_frontend_settings",
        return_value={"hcc_url": "https://default-3di-api.example.com"}
    )
    
    result = get_threedi_api()
    
    # Verify the frontend settings URL was used (not empty override)
    mock_api_client.assert_called_with("token", "https://default-3di-api.example.com")
    assert result is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
docker compose run --rm qgis pytest tests/test_generic.py::test_get_threedi_api_uses_override_when_set -v
```

Expected: FAILED (function modified but not yet; old behavior)

- [ ] **Step 3: Modify get_threedi_api() in utils/generic.py**

Open `rana_qgis_plugin/utils/generic.py`. Find the `get_threedi_api()` function (around line 121-126). Replace it with:

```python
def get_threedi_api():
    """
    Get a 3Di API client.
    
    Retrieves the 3Di API URL from:
    1. QgsSettings hcc_url override (if set and non-empty)
    2. Frontend settings hcc_url (default)
    
    Returns:
        ThreediApi client configured with the resolved URL and user's API token.
    """
    _, personal_api_token = get_3di_auth()
    
    # Check for hcc_url override first
    hcc_url_override = get_hcc_url_override()
    if hcc_url_override:
        api_url = hcc_url_override.rstrip("/")
    else:
        # Fall back to frontend settings
        frontend_settings = get_frontend_settings()
        api_url = frontend_settings["hcc_url"].rstrip("/")
    
    threedi_api = get_api_client_with_personal_api_token(personal_api_token, api_url)
    return threedi_api
```

Make sure `get_hcc_url_override` is imported at the top of the file. If it's not already imported from `utils.settings`, add:

```python
from rana_qgis_plugin.utils.settings import get_hcc_url_override
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
docker compose run --rm qgis pytest tests/test_generic.py::test_get_threedi_api_uses_override_when_set tests/test_generic.py::test_get_threedi_api_uses_frontend_settings_when_no_override tests/test_generic.py::test_get_threedi_api_uses_frontend_settings_when_override_empty -v
```

Expected: PASSED (all three tests)

- [ ] **Step 5: Run all existing generic tests to ensure no regression**

```bash
docker compose run --rm qgis pytest tests/test_generic.py -v
```

Expected: All tests pass (no regression in existing functionality)

- [ ] **Step 6: Commit**

```bash
git add rana_qgis_plugin/utils/generic.py tests/test_generic.py
git commit -m "Modify get_threedi_api() to check hcc_url override in QgsSettings"
```

---

### Task 4: Add Advanced section to Settings Dialog

**Files:**
- Modify: `rana_qgis_plugin/widgets/settings_dialog.py`

- [ ] **Step 1: Locate the Settings Dialog initialization code**

Open `rana_qgis_plugin/widgets/settings_dialog.py`. Find the `__init__` method and the section where UI elements are created. You're looking for where form elements are added to the dialog (e.g., labels, text fields for base_url, working_dir, etc.).

- [ ] **Step 2: Add imports**

At the top of `settings_dialog.py`, add:

```python
from rana_qgis_plugin.utils.settings import get_advanced_settings
```

- [ ] **Step 3: Locate the setupUi method or equivalent**

Find where the UI is being constructed. Look for methods that add widgets (QLabel, QLineEdit, etc.) to the dialog layout.

- [ ] **Step 4: Add Advanced section at the bottom of the form**

Before the dialog buttons (OK, Cancel), add code to create the Advanced section. Find the layout object (likely `self.layout` or `layout`) and add:

```python
# Add Advanced settings section if any are configured
advanced_settings = get_advanced_settings()
if advanced_settings:
    # Add spacing before advanced section
    spacer = QSpacing()
    layout.addSpacing(15)
    
    # Add "Advanced" header
    advanced_header = QLabel("Advanced")
    advanced_header_font = advanced_header.font()
    advanced_header_font.setBold(True)
    advanced_header_font.setPointSize(advanced_header_font.pointSize() + 1)
    advanced_header.setFont(advanced_header_font)
    layout.addWidget(advanced_header)
    
    # Add each advanced setting as read-only text
    for setting_name, setting_value in advanced_settings.items():
        # Format the setting name for display (convert hcc_url to "HCC URL")
        display_name = setting_name.replace("_", " ").title()
        label = QLabel(f"{display_name}: {setting_value}")
        label.setStyleSheet("color: gray;")  # Gray text to indicate read-only
        layout.addWidget(label)
```

At the top of the file, make sure you have the necessary imports:

```python
from PyQt5.QtWidgets import QLabel, QSpacing
```

(These may already be imported; check existing imports first.)

- [ ] **Step 5: Test the Settings Dialog manually**

1. Build the Docker image and start QGIS
2. Manually set `hcc_url` in QGIS config file (location depends on your OS)
3. Open the Settings Dialog in the plugin
4. Verify the Advanced section appears with the hcc_url value
5. Remove `hcc_url` from config and reopen Settings Dialog
6. Verify Advanced section is hidden

```bash
docker compose build
docker compose up -d qgis
# Manual testing in GUI
docker compose down
```

- [ ] **Step 6: Commit**

```bash
git add rana_qgis_plugin/widgets/settings_dialog.py
git commit -m "Add read-only Advanced section to Settings Dialog for advanced settings"
```

---

### Task 5: Run full test suite and verify no regressions

**Files:**
- Test: All test files

- [ ] **Step 1: Run all unit tests**

```bash
docker compose run --rm qgis pytest tests/ -v
```

Expected: All tests pass (no failures or errors)

- [ ] **Step 2: Run pre-commit hooks to check code style**

```bash
cd /home/margriet/src/rana-qgis-plugin
pre-commit run --all-files
```

Expected: All pre-commit checks pass (no linting errors)

- [ ] **Step 3: Verify no breaking changes by reviewing modified files**

Run git diff to review all changes:

```bash
git diff HEAD~5..HEAD
```

Scan for any unintended changes or side effects. Verify:
- Import statements are correct
- Function signatures match test expectations
- No typos or syntax errors

- [ ] **Step 4: Create summary commit if needed**

If all tests pass and no regressions found, create a summary commit:

```bash
git log --oneline -6
```

Review the 6 most recent commits to verify they align with the design.

---

## Implementation Notes

1. **Testing Strategy**: All tasks follow TDD — write failing test first, then implement.
2. **QgsSettings key**: Uses `"Rana/hcc_url"` (follows existing pattern in codebase)
3. **Empty string handling**: Treated as falsy (empty override), falls back to frontend_settings
4. **UI Display**: Read-only advanced settings in Settings Dialog, no edit controls
5. **No validation**: URL validation is skipped; power users are responsible for correctness
6. **Extensibility**: `get_advanced_settings()` makes it easy to add more settings in future

## Testing Checklist

- [ ] Unit tests pass for `get_hcc_url_override()`
- [ ] Unit tests pass for `get_advanced_settings()`
- [ ] Unit tests pass for `get_threedi_api()` override behavior
- [ ] All existing tests pass (no regression)
- [ ] Pre-commit hooks pass
- [ ] Manual testing: Settings Dialog shows Advanced section when hcc_url is set
- [ ] Manual testing: Settings Dialog hides Advanced section when hcc_url is not set
- [ ] Manual testing: `get_threedi_api()` uses override URL when set
