# Feature Specification: Open files in file browser

**Created**: 2026-05-11
**Status**: Planned

## User Scenarios & Testing

### User Story 1 - Open local file/folder from FilesBrowser context menu (Priority: P1)

User right-clicks a file in FilesBrowser and selects "Open in file browser" to navigate to the local folder or file in the OS file explorer.

**Why this priority**: Core functionality — the primary way users will access this feature.

**Independent Test**: Right-click a downloaded file in FilesBrowser, select "Open in file browser", verify OS file explorer opens at the correct location.

**Acceptance Scenarios**:

1. **Given** a regular file (vector/raster) that has been downloaded, **When** user right-clicks and selects "Open in file browser", **Then** the OS file explorer opens showing the local file location.
2. **Given** a scenario with downloaded results, **When** user right-clicks and selects "Open in file browser", **Then** the OS file explorer opens the results folder.
3. **Given** a schematisation with a locally present latest revision, **When** user right-clicks and selects "Open in file browser", **Then** the OS file explorer opens the revision folder.
4. **Given** a file that has NOT been downloaded, **When** user right-clicks, **Then** "Open in file browser" does NOT appear in the context menu.

---

### User Story 2 - Open local file/folder from FileView button (Priority: P1)

User views file details in FileView and clicks the "Open in file browser" button.

**Why this priority**: Same core functionality, alternative access point.

**Independent Test**: Select a downloaded file, verify button is visible in FileView. Select a non-downloaded file, verify button is hidden.

**Acceptance Scenarios**:

1. **Given** a file that exists locally, **When** user opens FileView, **Then** the "Open in file browser" button is visible and clicking it opens the OS file explorer.
2. **Given** a file that does NOT exist locally, **When** user opens FileView, **Then** the "Open in file browser" button is hidden.

---

### User Story 3 - Open revision folder from RevisionsView context menu (Priority: P2)

User right-clicks a schematisation revision in RevisionsView and selects "Open in file browser" to open the revision's local folder.

**Why this priority**: Extends the feature to revisions — useful but secondary to the main file browsing flow.

**Independent Test**: Right-click a revision that has been downloaded, verify "Open in file browser" appears and opens the correct revision folder.

**Acceptance Scenarios**:

1. **Given** a revision that exists locally, **When** user right-clicks in RevisionsView, **Then** "Open in file browser" appears and opens the revision folder.
2. **Given** a revision that does NOT exist locally, **When** user right-clicks in RevisionsView, **Then** "Open in file browser" does NOT appear.

---

### Edge Cases

- What happens when the local folder/file was deleted after the browser was populated? The action will be visible but `QDesktopServices.openUrl` will fail silently (OS behavior). Acceptable for now.
- What happens when `hcc_working_dir()` is not configured? No local schematisation/scenario paths can be resolved — action is hidden. Same for scenarios without complete meta data.
- What happens for non-3Di scenarios? Falls back to `get_local_dir_structure` path (same as regular files but checks dir existence).

## Requirements

### Functional Requirements

- **FR-001**: System MUST add `OPEN_IN_FILE_BROWSER` to `FileAction` enum.
- **FR-002**: System MUST compute and cache the local path on each file item during `fetch_and_populate` (FilesBrowser).
- **FR-003**: System MUST show "Open in file browser" in FilesBrowser context menu only when local path exists.
- **FR-004**: System MUST show "Open in file browser" button in FileView only when local path exists.
- **FR-005**: System MUST show "Open in file browser" in RevisionsView context menu only when local revision folder exists.
- **FR-006**: System MUST open the path via `QDesktopServices.openUrl(QUrl.fromLocalFile(path))`.

## Design Decisions

### Local path resolution

Paths are resolved at populate time and cached on the file dict to avoid repeated API calls on context menu open.

| File type | API calls at populate | Local path | Existence check |
|-----------|----------------------|------------|-----------------|
| Other files (vector/raster) | 0 | `get_local_file_path(project_slug, file_id)` | file exists |
| Schematisation | 1 (`get_threedi_schematisation`) | `LocalRevision(local_schematisation, revision_number).main_dir` using `hcc_working_dir()` | dir exists |
| Scenario | 1 (`get_tenant_file_descriptor`) | `get_threedi_schematisation_simulation_results_folder(...)` for 3Di, `get_local_dir_structure(...)` for non-3Di | dir exists |

For schematisations, `list_local_schematisations(hcc_working_dir())` is used to find the `LocalSchematisation`, then the latest revision number from the API response determines which `LocalRevision` folder to check.

### Open target

- Scenario: open `local_dir` (results folder)
- Schematisation: open `local_dir` (revision folder)
- Other files: open `local_dir` (containing folder from `get_local_dir_structure`)

### Show/hide pattern

Follows the existing convention: actions are shown/hidden, not enabled/disabled. The action is excluded from `get_file_actions_for_data_type` results (or filtered in the UI) when no local path exists.

### No DownloadContext or ScenarioInfo reuse

Path resolution is done directly from meta/file data to avoid unnecessary API calls (`ScenarioInfo` constructor calls the 3Di API) and unnecessary coupling to download logic.

## Components to modify

- `widgets/utils_file_action.py`: Add `OPEN_IN_FILE_BROWSER` enum member. Add to action lists. No signal needed (handled directly like `OPEN_IN_BROWSER`).
- `widgets/files_browser.py`: Compute and cache local path in `fetch_and_populate`. Handle action in `menu_requested`. Add `open_in_file_browser()` method.
- `widgets/file_view.py`: Show/hide button based on cached local path. Handle click.
- `widgets/revisions_view.py`: Add context menu entry. Resolve revision folder path. Handle click.

## Success Criteria

- **SC-001**: User can open the local folder/file location for any downloaded file from FilesBrowser context menu.
- **SC-002**: User can open the local folder/file location from FileView button.
- **SC-003**: User can open a revision folder from RevisionsView context menu.
- **SC-004**: The action is hidden when no local file/folder exists.
- **SC-005**: No noticeable delay when populating the file list due to local path resolution.
