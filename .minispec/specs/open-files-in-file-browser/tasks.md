---
feature: open-files-in-file-browser
status: planned
created: 2026-05-11
chunk_size: medium
total_tasks: 7
estimated_lines: 230
---

# Open Files in File Browser — Tasks

## Overview
Add an "Open in file browser" action that opens the local folder/file in the OS file explorer, available in FilesBrowser context menu, FileView button, and RevisionsView context menu.

## Task List

### Foundation

#### Task 1: Add OPEN_IN_FILE_BROWSER to FileAction
- **Estimate:** ~20 lines
- **Files:** `rana_qgis_plugin/widgets/utils_file_action.py`
- **Description:** Add `OPEN_IN_FILE_BROWSER` enum member. Add to relevant action lists in `get_file_actions_by_data_type` and `get_scenario_actions`.
- **Depends on:** None
- **Acceptance:** New action appears in action lists for all file types. Existing tests still pass.

#### Task 2: Add path resolution functions
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/utils/generic.py`
- **Description:** Add two functions:
  - `get_local_schematisation_revision_dir(schematisation_id, revision_number)` — looks up `LocalSchematisation` in `hcc_working_dir()`, returns `Path` to `LocalRevision.main_dir` or `None`.
  - `get_local_scenario_dir(meta)` — wraps the above, appending `results/{simulation_name} ({simulation_id})`. Falls back to `get_local_dir_structure` for non-3Di scenarios.
- **Depends on:** None
- **Acceptance:** Functions return correct paths for valid input and `None` for incomplete/missing data.

#### Task 3: Unit tests for path resolution
- **Estimate:** ~40 lines
- **Files:** `tests/`
- **Description:** Test `get_local_schematisation_revision_dir` and `get_local_scenario_dir` with mocked filesystem/settings. Test action list inclusion for `OPEN_IN_FILE_BROWSER`.
- **Depends on:** Task 1, Task 2
- **Acceptance:** Tests pass. Cover happy path, missing working dir, missing local schematisation, incomplete meta.

### Core Implementation

#### Task 4: Compute and cache local path at populate time in FilesBrowser
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/widgets/files_browser.py`
- **Description:** In `fetch_and_populate` loop, resolve local path per file:
  - `scenario` → fetch descriptor, call `get_local_scenario_dir(meta)`
  - `threedi_schematisation` → fetch schematisation, call `get_local_schematisation_revision_dir(id, latest_revision_number)`
  - other → `get_local_file_path(project_slug, file_id)`
  
  Store result on file dict (e.g. `file["local_path"]`).
- **Depends on:** Task 2
- **Acceptance:** After populate, file dicts contain `local_path` key with correct path or `None`.

#### Task 5: Add context menu entry and handler in FilesBrowser
- **Estimate:** ~20 lines
- **Files:** `rana_qgis_plugin/widgets/files_browser.py`
- **Description:** In `menu_requested`, show "Open in file browser" only when `file["local_path"]` exists on disk. Add `open_in_file_browser(path)` method using `QDesktopServices.openUrl(QUrl.fromLocalFile(path))`. For scenarios/schematisations open `local_path` (dir), for other files open `local_path.parent` (containing dir).
- **Depends on:** Task 1, Task 4
- **Acceptance:** Context menu item appears only for locally present files. Clicking opens OS file explorer.

#### Task 6: Add button and handler in FileView
- **Estimate:** ~30 lines
- **Files:** `rana_qgis_plugin/widgets/file_view.py`
- **Description:** Add button for `OPEN_IN_FILE_BROWSER` in `get_file_action_buttons`. Show/hide in `update_file_action_buttons` based on `file["local_path"]` existence. Handle click → open in file browser.
- **Depends on:** Task 1, Task 4
- **Acceptance:** Button visible only when local path exists. Clicking opens OS file explorer.

#### Task 7: Add context menu entry in RevisionsView
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/widgets/revisions_view.py`
- **Description:** In `menu_requested`, resolve revision folder via `get_local_schematisation_revision_dir(schematisation_id, revision.number)`. Show "Open in file browser" only when folder exists. Handle click → open in file browser.
- **Depends on:** Task 2
- **Acceptance:** Context menu item appears only for locally present revisions. Clicking opens OS file explorer at the revision folder.

## Notes
- If populate-time path resolution causes noticeable slowdown (API calls for scenarios/schematisations), consider deferring to background thread in a follow-up.
- `QDesktopServices.openUrl(QUrl.fromLocalFile(...))` is cross-platform (Windows/Linux/macOS).
- Non-3Di scenarios without simulation meta fall back to `get_local_dir_structure` path.

## Manual Testing
- Download a file, right-click → "Open in file browser" → OS explorer opens at correct location
- Check that action is hidden for files not yet downloaded
- Test for scenario, schematisation, and regular file types
- Test revision context menu in RevisionsView

## Progress
- [x] Task 1: Add OPEN_IN_FILE_BROWSER to FileAction
- [x] Task 2: Add path resolution functions
- [x] Task 3: Unit tests for path resolution
- [x] Task 4: Compute and cache local path at populate time in FilesBrowser
- [x] Task 5: Add context menu entry and handler in FilesBrowser
- [x] Task 6: Add button and handler in FileView
- [x] Task 7: Add context menu entry in RevisionsView
