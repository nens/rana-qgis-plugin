---
feature: feat_451_simple_context_menu_actions
status: complete
created: 2026-08-14
chunk_size: adaptive
total_tasks: 5
estimated_lines: 145
---

# Simple Context Menu Actions Tasks

## Overview
Wire up rename (files + folders), delete (files), and open-in-browser context menu actions on Rana browser items. Introduce tree-mutation signals on Loader for future layer panel integration.

## Task List

### Foundation

#### Task 1: Spike — Verify QgsDataItemGuiProvider rename dispatch
- **Estimate:** ~20 lines
- **Files:** `data_items/gui_provider.py` (temporary), `plugin.py` or equivalent
- **Description:** Register a minimal `QgsDataItemGuiProvider` subclass that logs when `rename()` is called. Add `Qgis.BrowserItemCapability.Rename` to one item class. Verify QGIS shows inline rename UI (F2 / slow double-click) and calls our provider's `rename()`.
- **Depends on:** None
- **Acceptance:** F2 on a Rana item triggers a log message from our provider
- **Evidence:** Manual test confirms inline rename UI appears and our `rename()` is invoked
- **Fallback:** If dispatch doesn't work as expected, switch to dialog-based rename via existing `RENAME` QAction. Only Task 3 changes; other tasks are unaffected.

#### Task 2: Add Loader mutation methods and signals
- **Estimate:** ~30 lines
- **Files:** `loader.py`
- **Description:** Add two methods and two signals to Loader:
  - `rename_item(project_id, old_path, new_name, is_folder) -> bool` — calls `api.move_file()` or `api.move_directory()`, emits `item_renamed` on success
  - `delete_file(project_id, path) -> bool` — calls `api.delete_tenant_project_file()`, emits `item_deleted` on success
  - `item_renamed = pyqtSignal(str, str, bool)` — `(old_path, new_path, is_folder)`
  - `item_deleted = pyqtSignal(str, bool)` — `(path, is_folder)`
- **Depends on:** None
- **Acceptance:** Methods call the correct API functions and emit signals only on success
- **Evidence:** Unit tests pass (mocking only `api.*` calls)

### Core Implementation

#### Task 3: Implement RanaDataItemGuiProvider with rename logic
- **Estimate:** ~50 lines
- **Files:** `data_items/gui_provider.py`, `data_items/file_item.py`, `data_items/folder_item.py`, `plugin.py`
- **Description:** Evolve spike into full implementation:
  - `rename(item, name, context) -> bool` — validate new name (non-empty, no illegal chars, no duplicate sibling), call `Loader.rename_item()`, refresh `item.parent()` on success
  - Add `Qgis.BrowserItemCapability.Rename` to both `RanaFileDataItem` and `RanaFolderDataItem`
  - Register provider in `initGui()`, unregister in `unload()`
- **Depends on:** Task 1 (spike confirms approach), Task 2 (Loader methods exist)
- **Acceptance:** Inline rename works for both files and folders; invalid names show error; tree refreshes with new name
- **Evidence:** Manual test — rename a file and a folder, verify name changes in tree and on Rana

#### Task 4: Wire delete action [P]
- **Estimate:** ~30 lines
- **Parallel:** Can run with Task 5
- **Files:** `data_items/file_item.py`
- **Description:** Connect existing `DELETE` QAction in `RanaFileDataItem.actions()` to a handler that:
  1. Shows `QMessageBox.question()` confirmation
  2. Calls `Loader.delete_file()`
  3. On success, calls `self.parent().refresh()`
- **Depends on:** Task 2
- **Acceptance:** Delete shows confirmation, removes file on Rana, tree refreshes without the item
- **Evidence:** Manual test — delete a file, confirm dialog appears, file disappears from tree

#### Task 5: Wire open-in-browser action [P]
- **Estimate:** ~15 lines
- **Parallel:** Can run with Task 4
- **Files:** `data_items/file_item.py`
- **Description:** Connect existing `OPEN_IN_BROWSER` QAction to a handler that calls `api.get_tenant_file_url()` then `QDesktopServices.openUrl(QUrl(url))`. Show error dialog if URL fetch fails. No Loader involvement.
- **Depends on:** None
- **Acceptance:** Right-click → Open in browser opens the correct URL in the system browser
- **Evidence:** Manual test — action opens browser with correct Rana file URL

## Notes
- If the spike (Task 1) fails, fall back to dialog-based rename via existing `RENAME` QAction — only Task 3 changes
- Name validation rules: check legacy `rename_file()` and Rana API docs during Task 3 implementation
- Open question from design: should Open in browser work for folders too? Currently scoped to files only.
- Prefix-based path remapping contract is documented in decision `20260814-1002` for future layer panel subscribers

## Progress
- [x] Task 1: Spike — Verify QgsDataItemGuiProvider rename dispatch
- [x] Task 2: Add Loader mutation methods and signals
- [x] Task 3: Implement RanaDataItemGuiProvider with rename logic
- [x] Task 4: Wire delete action
- [x] Task 5: Wire open-in-browser action
