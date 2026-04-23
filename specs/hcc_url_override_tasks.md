---
feature: hcc_url_override
status: planned
created: 2026-04-23
chunk_size: medium
total_tasks: 5
estimated_lines: 220
---

# HCC URL Override Configuration Tasks

## Overview
This task list implements support for overriding the 3Di API URL via QgsSettings, with a read-only Advanced section in the Settings Dialog. The work spans three main areas: settings module functions, generic utilities modification, and Settings Dialog UI updates.

## Task List

### Task 1: Add `get_hcc_url_override()` to settings.py
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/utils/settings.py`, `tests/test_settings.py`
- **Description:** Create a new getter function that retrieves `hcc_url` from QgsSettings. Includes unit tests for: not set (returns None), set with value, set to empty string.
- **Depends on:** None
- **Acceptance:** All three unit tests pass

### Task 2: Add `get_advanced_settings()` to settings.py
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/utils/settings.py`, `tests/test_settings.py`
- **Description:** Create a function that collects all advanced settings with values. Only includes non-empty settings. Includes unit tests for: empty case, individual settings (hcc_url and use_plugin_excepthook), multiple settings, and empty value filtering.
- **Depends on:** Task 1
- **Acceptance:** All five unit tests pass

### Task 3: Modify `get_threedi_api()` to use hcc_url override
- **Estimate:** ~50 lines
- **Files:** `rana_qgis_plugin/utils/generic.py`, `tests/test_generic_threedi_api.py`
- **Description:** Update function to check for hcc_url override before falling back to frontend_settings. Add import for `get_hcc_url_override`. Includes unit tests for: override set, no override (None), empty override (falls back).
- **Depends on:** Task 1
- **Acceptance:** All three new tests pass, existing tests still pass (no regression)

### Task 4: Add Advanced section to Settings Dialog
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/widgets/settings_dialog.py`
- **Description:** Add import for `get_advanced_settings`. Create Advanced QGroupBox dynamically only when settings exist. Display each setting as read-only text, styling consistent with existing dialog (no hardcoded colors).
- **Depends on:** Task 2
- **Acceptance:** Settings Dialog shows/hides Advanced section correctly based on settings presence

### Task 5: Verify implementation and run full test suite
- **Estimate:** ~30 lines
- **Files:** All test files
- **Description:** Run full unit test suite to ensure no regressions. Verify all new tests pass. Run pre-commit hooks.
- **Depends on:** Tasks 1-4
- **Acceptance:** All tests pass, pre-commit checks pass

---

## Notes
- Medium chunk size (~40-60 lines per task) for comfortable review
- Tests bundled with implementation for each task
- UI styling kept consistent with existing dialog components (no hardcoded colors)
- Manual testing deferred until PR review
- Linear dependency chain with Task 5 as integration point

## Progress
- [ ] Task 1: Add `get_hcc_url_override()` to settings.py
- [ ] Task 2: Add `get_advanced_settings()` to settings.py
- [ ] Task 3: Modify `get_threedi_api()` to use hcc_url override
- [ ] Task 4: Add Advanced section to Settings Dialog
- [ ] Task 5: Verify implementation and run full test suite
