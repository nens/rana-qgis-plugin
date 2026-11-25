---
feature: feat_3126_choose_sim_result_destination
status: planned
created: 2026-11-25
chunk_size: adaptive
total_tasks: 4
estimated_lines: 445
---

# Choose Simulation Result Destination Tasks

**Input**: `.minispec/specs/feat_3126_choose_sim_result_destination/design.md`
**Branch**: `feat_3126_choose_sim_result_destination`

## Overview

Phase 1 of the design: an optional results folder on the wizard's name page,
chosen with a Rana folder picker that supports virtual (not-yet-existing)
folders. The chosen folder travels on `NewSimulation.results_folder` and is
used by the simulation tracker to build `outputs.results.id`. Phase 2 (typed
input) is deferred; see Notes.

Estimates: ~265 lines of code, ~180 lines of tests.

## Task List

### Foundation

#### Task 1: `results_folder` on `NewSimulation`, used by the tracker [P]
- **Estimate:** ~15 lines of code, ~30 lines of tests
- **Parallel:** Can run with Task 2
- **Files:** `rana_qgis_plugin/simulation/data_models/simulation_data_models.py`,
  `rana_qgis_plugin/loader.py`, `tests/loader/test_simulation.py`
- **Description:**
  - Add `results_folder: str` to `NewSimulation`, as a required field after
    `duration`. It holds a project path with a trailing slash, e.g.
    `models/river/results/`.
  - `SimulationWizard` gets a `schematisation_folder` argument (trailing
    slash), passed from `Loader.start_simulation`. It sets
    `self.results_folder` to it on init. `run_new_simulation` reads
    `self.results_folder`, so the default is decided in one place and the
    picker later only changes `self.results_folder`.
  - In `start_simulation_tracker_process`, build the output id from
    `simulation.results_folder` only. The file name stays
    `{name}_{id}_results.zip`.
- **Depends on:** None
- **Acceptance:** The tracker receives `<results_folder><name>_<id>_results.zip`.
  Without a chosen folder, the wizard sets `results_folder` to the schematisation
  folder, so the default location is unchanged.
- **Evidence:** The tracker tests in `tests/loader/test_simulation.py` set
  `results_folder` on their fixtures and assert the output id. The wizard
  sets the default: a test or manual check that `run_new_simulation` passes
  the schematisation folder.

#### Task 2: `RanaFolderPicker`, browsing real folders [P]
- **Estimate:** ~110 lines of code, ~70 lines of tests
- **Parallel:** Can run with Task 1
- **Files:** `rana_qgis_plugin/simulation/rana_folder_picker.py` (new),
  `tests/simulation/test_rana_folder_picker.py` (new)
- **Description:**
  - `RanaFolderPicker(QDialog)` with the signature
    `(project, start_folder, list_folders=get_tenant_project_files, parent=None)`.
    `list_folders` can be replaced in tests.
  - A `QTreeWidget` with a single top-level item, the project root, labelled
    with the project name. You cannot go above it.
  - Each item's project path is derived from its ancestors, not stored.
  - On open: synchronously load and expand each level along `start_folder`,
    then select the target. Use a busy cursor
    (`QApplication.setOverrideCursor`).
  - Lazy loading: real folders get a placeholder child and are fetched on
    `itemExpanded`. Show folders only (`type == "directory"`), with the
    standard folder icon.
  - `Select` / `Cancel`. `selected_folder()` returns the project path with a
    trailing slash (`""` = root).
  - `NetworkUnavailableError` / `RanaFetchError` are shown in the dialog and
    not sent through the global `error_signals`. If the initial load fails,
    the dialog closes with a message.
- **Depends on:** None
- **Acceptance:** The picker opens at the start folder, shows only folders,
  loads subfolders on expand, has no item above the project root, and returns
  the selected path.
- **Evidence:** pytest-qt tests with a fake `list_folders`:
  - files are filtered out
  - the root is the only top-level item
  - the start folder is expanded and selected
  - expanding loads its children once
  - `selected_folder()` returns the right value
  - a fetch error on expand shows an error and keeps the dialog usable
  - a fetch error on the initial load closes the dialog with a message

### Core Implementation

#### Task 3: Virtual folders in the picker
- **Estimate:** ~80 lines of code, ~80 lines of tests
- **Files:** `rana_qgis_plugin/simulation/rana_folder_picker.py`,
  `tests/simulation/test_rana_folder_picker.py`
- **Description:**
  - `New folder…`, `Rename…` and `Delete` buttons. `Rename…` and `Delete` are
    enabled only when a virtual folder is selected.
  - Names are entered with `NameInputDialog`. The submit callback validates
    with `validate_item_name` plus a **case-insensitive** (`casefold()`)
    duplicate check against sibling folders, real or virtual. A rename skips
    the item itself.
  - `New folder…` on a real folder whose children are not loaded yet loads
    them first, so the duplicate check sees every existing sibling.
  - Virtual items:
    - flag in `Qt.ItemDataRole.UserRole`
    - `mActionNewFolder.svg` icon
    - italic font
    - tooltip "New folder, created when results are uploaded"
    - no placeholder child, and expanding never fetches
  - Nested virtual folders are allowed. Delete removes the subtree and selects
    the parent.
  - Expanding to the start path: path segments that don't exist on Rana become
    virtual items, so the wizard's current destination can be restored on
    reopen.
- **Depends on:** Task 2
- **Acceptance:** Users can create, nest, rename and delete virtual folders;
  real folders cannot be renamed or deleted. `foo` vs `Foo` is rejected.
  Nothing is sent to Rana. Reopening on a partly non-existent path shows the
  missing part as virtual folders.
- **Evidence:** pytest-qt tests:
  - create a nested virtual folder; `selected_folder()` returns the nested path
  - a case-only duplicate is rejected
  - a duplicate under a real folder that was never expanded is rejected
  - a case-only rename of the item itself is allowed
  - renaming a virtual parent changes the derived child path
  - delete removes the subtree
  - buttons are disabled for real folders
  - expanding a virtual folder calls `list_folders` zero times
  - a start path with missing segments creates virtual items

### Integration

#### Task 4: Results-folder row in the wizard
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/simulation/simulation_wizard/page_name.ui`,
  `rana_qgis_plugin/simulation/simulation_wizard.py`,
  `rana_qgis_plugin/loader.py`
- **Description:**
  - `page_name.ui`: a new row `Results folder:` with a read-only label,
    `Browse…` and `Clear`.
  - `NameWidget` holds `results_folder: str | None`. The label shows
    `/<path>` or `/<schematisation folder> (next to schematisation)`.
  - `Browse…` opens `RanaFolderPicker(project, results_folder or
    schematisation_folder)`. `Clear` resets the folder to `None`.
  - `SimulationWizard.__init__` gets `project` and `schematisation_folder`
    arguments.
  - `run_new_simulation` sets `new_simulation.results_folder` for every
    simulation (batch runs included).
  - `Loader.start_simulation` passes `project` and the folder part of
    `file_item["id"]`.
- **Depends on:** Task 1, Task 2 (Task 3 is needed for the full manual test)
- **Acceptance:** Choosing a folder in the wizard makes the results zip
  appear in that folder on Rana. With no choice, it appears next to the
  schematisation, as before.
- **Evidence:** The unit tests still pass. Manual UI paths:
  - Start a simulation from the schematisation context menu → name page →
    `Browse…` / `Select` / `Clear`; the label updates.
  - Run with an existing nested folder, a new (virtual) nested folder, the
    project root, and the default. Check where the zip appears in the Browser.
  - Reopen the picker after choosing a virtual folder. It shows that folder as
    virtual and selected. Only the last choice is restored.
  - A batch run (`_1`, `_2`) with a chosen folder.
  - Open the picker without a network connection.

## Notes

- The tracker output id is tested through the existing
  `start_simulation_tracker_process` tests, so no extraction is needed. This
  resolves that open question in the design.
- The project root is labelled with the project name (design open question,
  resolved here).
- Synchronous loading follows `ProjectsSelectionDialog.fetch_and_populate`.
- The picker lives next to the wizard in `rana_qgis_plugin/simulation/`.
- **Deferred (Phase 2):**
  - `resolve_results_folder(schematisation_folder, text)` with parametrized
    tests (see the table in the design).
  - Turn the label into a `QLineEdit` with live validation and block `Next`
    (`NamePage.isComplete`). The picker then writes relative text below the
    schematisation folder and absolute text (`/…`) elsewhere.
  - Decide how to handle a case mismatch between typed and existing folders
    (`Foo/` vs `foo/`).

## Progress
- [x] Task 1: `results_folder` on `NewSimulation`, used by the tracker
- [x] Task 2: `RanaFolderPicker`, browsing real folders
- [ ] Task 3: Virtual folders in the picker
- [ ] Task 4: Results-folder row in the wizard
