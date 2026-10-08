---
feature: feat_451_simple_context_menu_actions
status: complete
created: 2026-08-14
decisions:
  - 20260814-1000-rename-via-gui-provider
  - 20260814-1001-loader-mutation-methods-and-signals
  - 20260814-1002-prefix-based-path-remapping-contract
---

# Simple Context Menu Actions Design

## Overview

Wire up three context menu actions on Rana file/folder browser items: **rename**, **delete**, and **open in browser**. These actions exist in the `FileAction` enum and appear in menus already, but have no handlers connected. Additionally, introduce tree-mutation signals on `Loader` so that a future layer panel can track renames and deletes without coupling to the browser tree.

## User Stories

- As a user, I want to rename a file or folder in the Rana tree so I can organise my project
- As a user, I want to delete a file so I can remove obsolete data
- As a user, I want to open a file in my browser to view it in the Rana web interface

## Components

### RanaDataItemGuiProvider (new)

A `QgsDataItemGuiProvider` subclass registered with `QgsGui.dataItemGuiProviderRegistry()`.

Responsibilities:
- Implement `rename(item, name, context) -> bool` for `RanaFileDataItem` and `RanaFolderDataItem`
- Validate the new name (non-empty, no illegal characters, no duplicate sibling — matching legacy `rename_file()` validation logic)
- Call `Loader.rename_item()` on success
- Refresh `item.parent()` after a successful rename

QGIS handles the inline rename UI (F2 / slow double-click) automatically when an item declares `Qgis.BrowserItemCapability.Rename`. No custom input dialog needed.

Registration: `initGui()` registers the provider; `unload()` removes it. Care must be taken to unregister on unload to avoid stale provider references across plugin reloads.

**Implementation note — spike first**: the exact QGIS dispatch logic for which registered provider's `rename()` is called for a given item is not fully documented. A quick spike (register the provider, set the capability, log a call) should be done as the first implementation task to confirm the mechanism works as expected before writing the rest.

### Loader mutation methods and signals (modified)

New methods on `Loader`:
- `rename_item(project_id, old_path, new_name, is_folder) -> bool` — calls `api.move_file()` or `api.move_directory()`, emits `item_renamed` on success
- `delete_file(project_id, path) -> bool` — calls `api.delete_tenant_project_file()`, emits `item_deleted` on success

New pyqtSignals on `Loader`:
- `item_renamed = pyqtSignal(str, str, bool)` — `(old_path, new_path, is_folder)`
- `item_deleted = pyqtSignal(str, bool)` — `(path, is_folder)`

These are synchronous calls (no threading needed — the API functions return `bool` directly). Loader hosts them because:
1. Data items are ephemeral (recreated on every `refresh()`), so they cannot safely own long-lived signals that other panels subscribe to
2. Loader is the one persistent, shared object accessible across the plugin's lifetime
3. Co-locating mutation + signal emission ensures signals are only emitted on actual success

### Delete handler (on data item)

Connected via the existing `DELETE` QAction in `RanaFileDataItem.actions()`.

Flow: show `QMessageBox.question()` confirmation → call `Loader.delete_file()` → on success, `self.parent().refresh()`.

Files only (per scope). The `DELETE` action should not appear for folders (check current `file_actions.py` to confirm it's excluded from `get_folder_actions()`).

### Open in browser handler (on data item)

Connected via the existing `OPEN_IN_BROWSER` QAction. Fully synchronous, no Loader involvement.

Flow: `api.get_tenant_file_url(project_id, params)` → `QDesktopServices.openUrl(QUrl(url))`. Show error dialog if URL fetch fails.

### Capability flags (modified)

Add `Qgis.BrowserItemCapability.Rename` to the existing `setCapabilitiesV2()` calls in:
- `folder_item.py` (RanaFolderDataItem)
- `file_item.py` (RanaFileDataItem)

## Signal Contract (for future layer panel integration)

### Remapping rule

Subscribers (e.g. a future layer panel) **must use prefix-based path remapping**, not exact-match:

```python
if layer_path.startswith(old_path):
    layer_path = new_path + layer_path[len(old_path):]
```

This covers all cases:
- File renamed directly → exact match, prefix replacement still works
- Ancestor folder renamed → layer's path starts with the old folder path, prefix replacement updates it correctly
- Single layer from a multi-layer file, where the parent file is renamed → same prefix logic applies since the layer path is derived from the file path

The signal emits **one event for the renamed item itself**. Subscribers are responsible for checking whether any of their tracked paths fall under the renamed prefix.

### Delete contract

On `item_deleted(path, is_folder)`: subscribers should remove or invalidate any tracked items whose paths start with the deleted path (for files this is an exact match; for future folder-delete support it would be a prefix match).

## Refresh Strategy

- **Rename**: `item.parent().refresh()` — reloads siblings with corrected paths. Children of a renamed folder are rebuilt lazily by QGIS on next expansion via `createChildren()`.
- **Delete**: `item.parent().refresh()` — reloads siblings without the deleted item.
- Both match the existing pattern used for uploads (`refresh_callback=self.refresh_if_populated`).

## Files Changed

| File | Change |
|---|---|
| `data_items/gui_provider.py` | **New** — `RanaDataItemGuiProvider` class |
| `data_items/folder_item.py` | Add `Rename` capability; wire `DELETE` action (if folders gain delete later) |
| `data_items/file_item.py` | Add `Rename` capability; wire `DELETE` and `OPEN_IN_BROWSER` actions |
| `loader.py` | Add `rename_item()`, `delete_file()` methods + `item_renamed`, `item_deleted` signals |
| `plugin.py` (or equivalent init) | Register/unregister `RanaDataItemGuiProvider` |

## Open Questions

- **GuiProvider dispatch verification**: need a quick spike to confirm QGIS calls our provider's `rename()` for our custom data item types when they declare the `Rename` capability
- **Name validation rules**: what characters are illegal in Rana file/folder names? Check legacy `rename_file()` and/or Rana API docs
- **Open in browser for folders**: should `OPEN_IN_BROWSER` work for folders too, or files only? (Current scope says files only for delete, but doesn't specify for open-in-browser)
