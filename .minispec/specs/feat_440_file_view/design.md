---
feature: feat_440_file_view
 status: complete
created: 2026-08-10
decisions:
  - 20260810-1100-file-info-model-driven-ui
  - 20260810-1101-file-info-dialog-fetching
---

# View File Info Design

## Overview

Add a **View file info** action to every Rana file context menu. The action opens a read-only dialog based on the legacy `file_view`, while removing action buttons and rename functionality. The dialog fetches the file descriptor asynchronously when opened and when the user requests a refresh.

The initial presentation keeps the existing `QgsCollapsibleGroupBox` layout. A model-driven design ensures refresh updates the contents rather than recreating the group boxes. If QGIS group-box issues remain, the same models can support a later tabs or scrollable-form presentation.

## User Stories

### View file metadata (P1)

As a QGIS user, I want to open file information from a file's context menu so that I can inspect metadata without opening or modifying the file.

**Acceptance scenarios:**

- Given a file in the Rana Browser, when the user chooses **View file info**, then a dialog opens and displays the descriptor data.
- Given a generic file, when its information is displayed, then general metadata and applicable detailed metadata are shown.
- Given a scenario or schematisation, when its information is displayed, then all corresponding legacy metadata is shown, including scenario/schematisation-specific fields.

### Refresh file metadata (P1)

As a user, I want to refresh the dialog on demand so that I can inspect current server-side metadata.

**Acceptance scenarios:**

- Given an open file-info dialog, when the user presses Refresh, then the descriptor is fetched again and existing UI sections are updated in place.
- Given a fetch failure, when opening or refreshing, then the dialog remains usable and displays an understandable error state.

### Inspect related files and author (P2)

As a user, I want to see the file author/avatar and schematisation related files so that the complete legacy information view remains available.

**Acceptance scenarios:**

- Given descriptor author data, when the dialog is displayed, then the username and avatar are shown when available.
- Given a schematisation with related files, when its information is displayed, then the related-files table is shown.

## Scope

Included:

- Generic files, scenarios, and schematisations.
- General information, detailed metadata, scenario metadata, schematisation metadata, and related-files table shown by the legacy widget.
- Avatar display using the existing avatar cache/worker infrastructure.
- Asynchronous descriptor fetching on open and refresh.
- Read-only display.

Excluded:

- File action buttons.
- Rename.
- New actions for folders.
- Wiring any existing file actions beyond adding View file info.

## Components

### File context action

Add `VIEW_FILE_INFO` to `FileAction` and include it for every file type. The action creates and opens a `FileInfoDialog` for the selected file descriptor.

### File info dialog

`FileInfoDialog` is a `QDialog` containing the existing three logical sections:

- General
- More Information
- Related Files (schematisations)

The dialog owns stable widgets and updates their contents from the model. It contains a Refresh button and loading/error states, but no file action or rename controls.

### File info models

Use a base model and specialized models:

- `FileInfoModel`: generic file fields and common section data.
- `ScenarioFileInfoModel`: common fields plus scenario simulation metadata.
- `SchematisationFileInfoModel`: common fields plus creator, tags, revision, counts, and related files.

Models transform descriptor responses into display-ready sections, rows, and related-file records. The dialog does not contain data-type conditionals beyond selecting/rendering model-provided content.

### Background worker

Fetch the descriptor synchronously from the modal dialog on open and refresh. Use the existing avatar worker/cache only for avatar retrieval, which can arrive after the descriptor contents are displayed.

### Related-files table

The schematisation model exposes related-file records through a table model. The table is placed inside the Related Files group box and is updated when the descriptor refreshes.

## Data Model

The model exposes stable presentation data, conceptually:

- `InfoSection(title, rows)` for grouped key-value metadata.
- `InfoRow(label, value, error state and optional tooltip)` for display rows.
- Related-file records containing name, type, size, and optional icon metadata.
- Author identity and avatar state.

The exact descriptor schema remains the API response schema; models normalize absent or malformed values into safe display values rather than allowing rendering failures.

## API/Interface

- Existing `get_tenant_file_descriptor(descriptor_id)` supplies the descriptor.
- `FileInfoDialog(file_data, error_signals, parent=None)` opens the view. The file dictionary supplies the descriptor ID, data type, and general file metadata.
- The context action invokes the dialog and starts its initial fetch.
- Refresh invokes the same fetch path and replaces model contents without rebuilding the section containers.

## Error and lifecycle handling

- Show a busy/loading state while a fetch is active.
- Disable the Refresh button during the synchronous request and re-enable it afterwards.
- Surface fetch errors in the dialog and keep Refresh available.
- No descriptor worker results need lifecycle management because descriptor fetching occurs on the dialog's UI thread.

## Scope challenge and fallback

The first implementation intentionally keeps the group boxes because the model/view split makes a presentation change inexpensive. If group-box problems persist, replace only the dialog renderer with tabs or a plain scrollable form; the descriptor worker and specialized models remain unchanged.

## Manual testing paths

- Right-click a generic vector, raster, and other file; open View file info and verify common metadata.
- Open a scenario and verify simulation metadata.
- Open a schematisation and verify creator, tags, revision/count information, avatar, and related-files table.
- Press Refresh after server-side metadata changes and verify the same dialog updates without rebuilding sections.
- Simulate a descriptor failure on open and refresh; verify loading/error behavior and that QGIS remains responsive.
