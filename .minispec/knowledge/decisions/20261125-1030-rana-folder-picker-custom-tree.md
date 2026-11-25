---
type: decision
id: 20261125-1030-rana-folder-picker-custom-tree
date: 2026-11-25
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/simulation/rana_folder_picker.py
  - rana_qgis_plugin/simulation/simulation_wizard.py
tags: [simulation, wizard, results, destination, picker, ui]
participants: [margriet, agent]
---

# Rana folder picker as a custom lazy tree

> Amended by `20261125-1050-picker-virtual-folders`: the picker can create,
> rename and delete virtual folders, and reopens at the current destination.

## Context

The results-folder field gets a `Browse…` button. `QFileDialog` can only browse
the local file system, so the picker has to be built separately. It must open at
the schematisation folder and must not go above the project root.

## Options Considered

- Flat list (one folder at a time with an Up button): simplest, but does not
  show the hierarchy.
- **Custom tree** (chosen): a `QTreeWidget` with the project as root.
- Reuse the QGIS Browser tree (`QgsBrowserTreeView` over the existing Rana data
  items): the only Rana-specific logic it would reuse is one
  `get_tenant_project_files` call. Drawbacks:
  - A new browser model creates root items for every provider and downloads the
    project list again.
  - Expanding to the start folder means waiting for each level to load on a
    background thread.
  - Files need to be filtered out with a proxy model.
  - Errors go through the global `error_signals` shared with the Browser panel.

## Decision

`RanaFolderPicker(QDialog)` in `simulation/rana_folder_picker.py`:

- A `QTreeWidget` whose single top-level item is the project root (`/`, labelled
  with the project name), so the project boundary follows from the structure.
- On open, it synchronously loads the folders along the path from the root to
  the start folder (one `get_tenant_project_files` call per level), expands
  them and selects the start folder.
- Other folders load when expanded (synchronous, busy cursor). A placeholder
  child shows the expand arrow until loading.
- Shows folders only (`type == "directory"`), with the standard folder icon.
- No "New folder" button. New folders are typed in the wizard field, and Rana
  creates them when the results are uploaded.
- Always opens at the schematisation folder, not at a previously chosen or
  typed folder.
- `Select` / `Cancel`. The result is a project path. In phase 1 the wizard shows
  it as the full project path. In phase 2 it is written into the field
  (relative below the schematisation folder, absolute elsewhere, see
  `20261125-1010-sim-result-destination-path-semantics`).
- Network or fetch errors are shown in the dialog. They are not sent through
  the global browser error signals.

## Consequences

- Self-contained widget that can be tested with a fake listing function.
- Synchronous loading is acceptable because each request lists only one folder.
  This follows the existing `ProjectsSelectionDialog.fetch_and_populate` pattern.
