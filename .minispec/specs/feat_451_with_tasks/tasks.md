---
feature: feat_451_with_tasks
status: cancelled
created: 2026-08-17
chunk_size: adaptive
total_tasks: 7
---

# Asynchronous Browser Mutations and Actions Tasks

> This feature is no longer relevant and is not scheduled for implementation.

## Task List

### Design and rename UI

#### Task 1: Add dialog-based rename
- **Files:** `data_items/file_item.py`, `data_items/folder_item.py`, new rename dialog module
- **Description:** Replace inline QGIS rename with a Rename context-menu action and
  an explicit dialog. Remove the GUI provider registration and Rename capability.
- **Acceptance:** Rename is started only from the context menu; cancel performs no request.

### Async operation foundation

#### Task 2: Define Loader operation lifecycle
- **Files:** `loader.py`, operation/task module, tests
- **Description:** Add stable operation IDs, started/succeeded/failed/finished
  signals, and active-operation state. Use the smallest background mechanism
  shared by the first operations; do not create a generic abstraction without
  demonstrated reuse.
- **Acceptance:** A network operation returns immediately and reports completion
  on the UI thread; active state is O(1) by operation ID.

#### Task 3: Migrate delete
- **Files:** `loader.py`, `data_items/file_item.py`, tests
- **Description:** Run delete asynchronously, disable the affected item's
  actions and descendants, refresh only after success, and re-enable on every
  completion path.
- **Acceptance:** Slow and failed deletes do not block QGIS; no stale-item error
  occurs after refresh.

#### Task 4: Migrate rename
- **Files:** `loader.py`, rename dialog/item modules, tests
- **Description:** Submit dialog-confirmed rename asynchronously using the same
  lifecycle as delete. Optimistically update the visible item's name after
  dialog confirmation, revert it on failure, refresh the parent after success,
  and restore the correct state if the item is recreated during the operation.
  Report failures without leaving stale optimistic state.
- **Acceptance:** Files and folders rename without inline-editor keyboard side
  effects and remain responsive during slow requests. The visible item updates
  immediately after confirmation, returns to its original name on failure, and
  the parent refreshes after success.

#### Task 5: Add asynchronous create-directory action
- **Files:** `data_items/folder_item.py`, `loader.py`, create-directory dialog,
  tests
- **Description:** Wire the existing Create directory action for root and
  nested folders. Show a folder-name dialog, submit creation through Loader,
  validate names and duplicates at the Loader/API boundary, refresh the
  selected folder after success, and report failures without blocking QGIS.
- **Acceptance:** Cancellation performs no request; successful creation adds
  the folder after refresh; failures leave the tree unchanged and actions
  recover.

### Other network-backed actions

#### Task 6: Audit and migrate remaining network-backed actions
- **Files:** Applicable action/data-item modules and tests
- **Description:** Review version history, downloads, WMS/results, file-info,
  and future connected context-menu actions. Migrate only operations that make
  network calls; leave local actions unchanged.
- **Acceptance:** Audit records each action as migrated, deferred, or local.

### Verification

#### Task 7: Verify responsive action lifecycle
- **Files:** Focused tests and MiniSpec notes
- **Description:** Run unit tests and manually verify slow, success, failure,
  cancellation, refresh, collapse, and data-item recreation paths.
- **Acceptance:** Tests pass and all manual paths have recorded results.
