---
type: decision
id: 20261125-1050-picker-virtual-folders
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

# Folder picker creates virtual folders only

Amends `20261125-1030-rana-folder-picker-custom-tree` (the "no New folder
button" and "always open at the schematisation folder" points).

## Context

Users want to choose a new folder as the results destination, including nested
new folders. Creating folders on Rana from the picker would leave empty folders
behind when the user changes their mind or cancels. Rana already creates missing
folders when the tracker uploads the results zip.

## Options Considered

- No folder creation in the picker (previous decision): new folders could only
  be typed in phase 2.
- Create folders on Rana immediately via `Loader.create_folder`: rejected,
  because abandoned choices leave a mess on Rana.
- **Virtual folders in the picker** (chosen): folders exist only as tree items
  until the results are uploaded.

## Decision

- `New folder…` adds a virtual child under the selected folder, real or
  virtual. Nothing is sent to Rana. Virtual items look different from real
  folders:
  - the QGIS "new folder" icon (`mActionNewFolder.svg`) instead of the plain
    folder icon
  - italic text
  - the tooltip "New folder, created when results are uploaded"
- Name validation when creating or renaming: `validate_item_name`, plus no
  duplicate among sibling folders (real or virtual), using a
  **case-insensitive** match (`casefold()`): if `foo` exists, `Foo` cannot be
  added. A rename skips the item itself, so changing only the case of a
  virtual folder's name is allowed.
- Virtual folders can be nested. Expanding a virtual folder never calls Rana.
- `Rename…` and `Delete` are enabled only when a virtual folder is selected.
  For real folders they are disabled. Delete removes the whole virtual
  subtree.
- An item's project path is derived from its ancestors when needed, not stored
  on the item, so renaming needs no path bookkeeping for its descendants.
- The tree itself is the bookkeeping. There is no separate pending list.
  Cancel discards everything.
- Reopen: the picker receives the wizard's current destination (or `None`). If
  set, it expands along that path. Real levels are loaded from Rana. Segments
  that do not exist become virtual items. The destination is then selected.
  Otherwise the picker opens at the schematisation folder. Only the current
  destination is passed in, so only the last chosen virtual path comes back.

## Consequences

- No stray folders on Rana. A folder only exists once results are uploaded into
  it.
- The same "expand to path, virtual where missing" logic also serves phase 2
  typed paths that do not exist yet.
- If someone creates a folder with the same name on Rana while the dialog is
  open, the result is still correct: the upload goes into the existing folder.
- Deferred to phase 2: how the picker handles a typed destination whose segment
  differs only in case from an existing folder (`Foo/` vs. `foo/`). See the
  feature design's open questions.
