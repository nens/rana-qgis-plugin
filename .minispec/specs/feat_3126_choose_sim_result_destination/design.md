---
feature: feat_3126_choose_sim_result_destination
status: planned
created: 2026-11-25
decisions:
  - 20261125-1000-sim-result-destination-separate-from-name
  - 20261125-1010-sim-result-destination-path-semantics
  - 20261125-1020-sim-result-destination-field-ux
  - 20261125-1030-rana-folder-picker-custom-tree
  - 20261125-1040-results-folder-on-new-simulation
  - 20261125-1050-picker-virtual-folders
---

# Choose Simulation Result Destination

## Overview

Add an optional results folder to the simulation wizard. It only changes where
the Rana `simulation_tracker` process saves `{name}_{id}_results.zip`. The 3Di
simulation name and the 3Di API are unchanged. Without a chosen folder,
results go next to the schematisation file, as they do today.

Phase 1 adds a Rana folder picker. Phase 2 makes the folder editable as text.

## Background

The results location is built by the plugin, not by 3Di
(`Loader.start_simulation_tracker_process`, `loader.py:~910`):

```python
"outputs": {"results": {"id": f"{schematisation_folder}{simulation_name}_{sim_id}_results.zip"}}
```

Typing `results/foo` as the simulation name works today only because the name is
copied into this path. The 3Di simulation is then also named `results/foo`.

## User Stories

- As a modeller, I want to choose a Rana folder for my simulation results so
  that results are organised in my project instead of piling up next to the
  schematisation.
- As a modeller, I want to browse the project's folders starting at my
  schematisation, so that I don't have to know or type the path.
- As a modeller, I want to leave the folder empty and get the current behaviour.
- (Phase 2) As a modeller, I want to type a folder (also a new one, and also
  with Windows-style `\`), so that I can work without browsing.

## User Flow

### Phase 1

Name page, below the existing rows:

```
Results folder:  /models/river/ (next to schematisation)   [Browse…] [Clear]
```

1. `Browse…` opens the picker at the current destination, or at the
   schematisation folder if none is set.
2. The user expands folders and optionally adds new (virtual) folders with
   `New folder…`, also nested. Virtual folders can be renamed or deleted.
3. The user selects a folder and clicks `Select`. The label shows the full
   project path, e.g. `/models/river/results/2026/`. Nothing is created on Rana.
4. `Clear` resets to the default.
5. On finish, every simulation (batch runs included) gets the chosen folder.
   Results end up at `<folder><name>_<id>_results.zip`. Rana creates missing
   folders on upload.

### Phase 2

The label becomes an editable line edit with the placeholder "Next to
schematisation (optional)". The picker writes into it. Typed text is validated
live. The error appears in red under the field, and `Next` is blocked while the
path is invalid.

## Components

### `RanaFolderPicker` (new, `simulation/rana_folder_picker.py`), phase 1

`QDialog` with a `QTreeWidget`, `New folder…`, `Rename…`, `Delete`, and
`Select` / `Cancel`.

```
+-- Select results folder ----------------------------------+
| v [folder] my-project (/)                                 |
|   v [folder] models                                       |
|     v [folder] river                                      |
|       > [folder] scenarios                                |
|       v [folder] results                                  |
|           [new-folder icon] 2026  (italic: virtual)       |
| [New folder…] [Rename…] [Delete]        [Cancel] [Select] |
+-----------------------------------------------------------+
```

Constructor: `RanaFolderPicker(project, start_folder: str,
list_folders=get_tenant_project_files, parent=None)`. The wizard passes the
current destination as `start_folder`, or the schematisation folder if none is
set. `list_folders` can be replaced for tests.

**Tree and loading**
- Single top-level item: the project root, labelled with the project name. You
  cannot go above it.
- On open: expands along `start_folder`. Each existing level is loaded synchronously (one `ls`
  per level). Segments that do not exist on Rana become virtual items. The
  target is selected.
- Other real folders load when expanded (synchronous, busy cursor). A
  placeholder child shows the expand arrow until loaded. Virtual folders never
  trigger a fetch.
- Shows folders only (`type == "directory"`), with the standard folder icon.

**Virtual folders (bookkeeping)**
- `New folder…` asks for a name (`NameInputDialog`) and adds a virtual child to
  the selected folder (real or virtual), then selects it. Nothing is sent to
  Rana. If the selected folder is real and its children are not loaded yet,
  they are loaded first, so the duplicate check sees every existing sibling.
- Virtual items are flagged (`Qt.ItemDataRole.UserRole`) and look different
  from real folders:
  - the QGIS "new folder" icon (`mActionNewFolder.svg`, via `getThemeIcon`)
  - italic text
  - the tooltip "New folder, created when results are uploaded"
- Name validation (create and rename): `validate_item_name`, plus no duplicate
  among sibling folders (real or virtual). The duplicate check is
  **case-insensitive** (`casefold()`): if `foo` exists, `Foo` is rejected. A
  rename skips the item itself, so changing only the case is allowed. Errors are
  shown in `NameInputDialog`, which stays open.
- `Rename…` / `Delete` are enabled only when a virtual folder is selected. For
  real folders they are disabled (greyed out). Delete removes the whole virtual
  subtree and selects the parent.
- An item's project path is derived from its ancestors when needed, so renames
  need no extra bookkeeping.
- The tree is the only state. Cancel discards all virtual folders. Because only
  the current destination is passed back in on reopen, only the last chosen
  virtual path comes back.

**Errors and result**
- `NetworkUnavailableError` / `RanaFetchError`: shown in the dialog. If the
  initial load fails, the dialog closes with a message. Errors are not sent
  through the global browser `error_signals`.
- Result: the selected project path, with a trailing slash (`""` = project
  root).

### Name page (`page_name.ui`, `NameWidget`, `NamePage`)

- Phase 1: a new row with a read-only label, `Browse…` and `Clear`. `NameWidget`
  holds the chosen folder (`str | None`).
- Phase 2: the label becomes a `QLineEdit` plus a red error label.
  `NamePage.isComplete()` also requires a valid results folder. The picker
  result is written as text: relative if below the schematisation folder,
  absolute (`/…`) otherwise.

### `resolve_results_folder` (new pure function), phase 2

```python
def resolve_results_folder(schematisation_folder: str, text: str) -> tuple[str | None, str | None]:
    """Return (project path with trailing slash, None), or (None, error message).

    Empty text returns (None, None), which means the default location.
    """
```

| Input | Result (schematisation in `models/river/`) |
|---|---|
| `""`, whitespace | `None` (default) |
| `results`, `./results`, `.\results` | `models/river/results/` |
| `/shared/results`, `\shared\results` | `shared/results/` |
| `../shared` | `models/shared/` |
| `../../..` | error: above project root |
| `C:\data`, `\\server\x` | error: not a Rana project path |
| `a/ b /c` | `models/river/a/b/c/` (segment whitespace trimmed) |
| `my results` | `models/river/my results/` |

Normalisation: `\` → `/`; empty and `.` segments dropped; whitespace around
each segment trimmed; `..` resolved and bounded by the project root; each
remaining segment checked with `validate_item_name`. No extra Windows
character rules, because local downloads already sanitize them
(`utils/local_paths.sanitize_path`).

Location: a small module next to the wizard (e.g.
`simulation/results_folder.py`), so it can be unit tested without Qt.

### `SimulationWizard`

- New constructor arguments `project: dict` (the picker needs the project name
  for the root label) and `schematisation_folder: str`
  (the folder part of `file_item["id"]`, with a trailing slash).
- `run_new_simulation` sets `results_folder` on every `NewSimulation`.

### `Loader`

- `start_simulation` passes `project` and the schematisation folder to
  the wizard.
- `start_simulation_tracker_process` uses `simulation.results_folder` only.
  The default (schematisation folder) is set by the wizard.

## Data Model

`dm.NewSimulation` gets:

```python
results_folder: str  # Rana project path with trailing slash, e.g. "models/river/results/"; required, default set by the wizard
```

## Testing

- Unit: `resolve_results_folder` (phase 2), covering the table above
  (parametrized).
- Unit: the tracker output id from `results_folder`, through the
  existing `start_simulation_tracker_process` tests.
- Unit (pytest-qt, fake `list_folders`): folders only; root boundary; expanding
  to the start folder; a failing initial load closes the dialog with a
  message; expanding to a partly non-existent destination
  creates virtual items; creating nested virtual folders; duplicate (including
  case-only, `foo` vs `Foo`) and invalid names are rejected, also under a real
  folder that was not expanded yet; renaming a virtual
  folder to a different case of its own name is allowed; renaming a virtual parent changes the derived child path;
  deleting removes the subtree; real folders cannot be renamed or deleted;
  expanding a virtual folder makes no fetch.
- Manual UI paths:
  - Start a simulation from the schematisation context menu → name page →
    Browse / Select / Clear.
  - Run with a nested folder, a project-root folder, and the default. Check
    where the zip appears in the Browser.
  - Batch simulations (`_1`, `_2`) with a chosen folder.
  - Picker with no network.
  - Phase 2: typed relative, absolute, `..`, Windows-style and invalid paths;
    `Next` is blocked while invalid.

## Out of Scope

- Creating folders on Rana from the picker (virtual only; Rana creates them on
  upload).
- Renaming or deleting real Rana folders in the picker.
- Remembering the last-used folder across wizard runs.
- A live preview of the resolved path.
- Saving the folder in simulation templates.
- The legacy plugin code.

## Open Questions

- **Deferred to phase 2:** a typed path like `Foo/` while `foo/` exists on Rana.
  Typing makes no network calls, so the field can't detect this. When the picker
  reopens on such a path, should it match the existing `foo` case-insensitively
  (and adopt its spelling), or show `Foo` as a virtual folder? Decide when
  phase 2 is picked up. Phase 1 is not affected, because the picker already
  rejects case-only duplicates.
- ~~The picker label for the project root~~: resolved, the project name.
- ~~Whether to extract the tracker output id~~: resolved, no. The existing
  `start_simulation_tracker_process` tests cover it.
