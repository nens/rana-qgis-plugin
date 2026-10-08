---
feature: file-info-view
branch: feat_440_file_view
 status: complete
created: 2026-08-10
chunk_size: adaptive
total_tasks: 3
---

# File Information View — Additional Tasks

## Overview

Complete the file information view with authenticated model metadata and the remaining related-files table layout fixes.

## Additional Tasks

### Task 1: Format related-files table columns
- **Files:** `rana_qgis_plugin/widgets/file_info_dialog.py`, related widget tests where practical
- **Description:** Configure column resize policies so Name, Type, and Size fit their contents while using dialog space sensibly. Long names must remain readable and compact values must not be clipped.
- **Acceptance:** Columns are readable at normal and resized dialog widths.

### Task 2: Include related-files section in scroll range
- **Files:** `rana_qgis_plugin/widgets/file_info_dialog.py`, related dialog/widget tests where practical
- **Description:** Fix expanded group-box/table sizing so the complete related-files section contributes to the scroll area's content size. Expanding or collapsing sections must update the scroll range correctly.
- **Depends on:** Task 1
- **Acceptance:** With More Information and Related Files expanded, users can scroll to the complete table without collapsing another section.

### Task 3: Retrieve model information with 3Di authentication
- **Files:** `rana_qgis_plugin/widgets/file_info_models.py`, authentication/API modules, related tests
- **Description:** Identify and use the existing 3Di authentication and API client path to retrieve the latest revision model. Populate simulation readiness, node count, and line count. Authentication or retrieval failures must remain safe `FieldValue` errors.
- **Acceptance:** Authenticated users see available model metadata; unavailable authentication or failed retrieval leaves the dialog usable and shows an error/unavailable state. Add unit tests for success and failure paths where feasible.

## Notes

- Manual UI testing paths: open file information for an authenticated schematisation, repeat unauthenticated, inspect long and short related-file names, resize the dialog, and scroll with all sections expanded.
- Do not add E2E tests without explicit permission.

## Progress

- [x] Task 1: Format related-files table columns
- [x] Task 2: Include related-files section in scroll range
- [x] Task 3: Retrieve model information with 3Di authentication
