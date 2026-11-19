---
feature: feat_517_upload_revision_from_disk
status: planned
created: 2026-11-19
chunk_size: adaptive
total_tasks: 5
estimated_lines: 330
---

# Upload Local WIP Revision from the File Context Menu: Tasks

## Overview

Implements `design.md` in this directory: a context-menu action that uploads the
local WIP of a schematisation without opening it, through two commit paths
(opened / stored) around a shared `save_revision` core, with a loader-level lock
allowing one revision upload per schematisation at a time.

## Task List

### Foundation

#### Task 1: Loader upload lock replaces the group lock
- **Estimate:** ~60 lines (incl. tests)
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/layer_management/layer_tree_menu.py`, `tests/loader/test_schematisation.py`
- **Description:** Add the in-memory set of uploading schematisation ids and `is_revision_upload_in_progress(schematisation_id)` to `Loader`. `save_revision` refuses to start when locked (message from the design), adds the id when the task is started, removes it on `taskCompleted` / `taskTerminated`. In `layer_tree_menu.py`, enable "Save revision" based on the loader lock and remove `_GROUP_LOCKED_KEY` and the group lock/unlock wiring (keep the `rana/revision_number` update for now).
- **Depends on:** None
- **Acceptance:** No reference to `_GROUP_LOCKED_KEY` or `rana/schematisation_uploading` remains; a second `save_revision` for the same id is refused while a task runs; the lock is released after completion and termination.
- **Evidence:** Unit tests: lock taken when task starts, released on `taskCompleted` and on `taskTerminated`, second call refused while locked, wizard cancel leaves no lock; `test_save_revision_requires_authenticated_api` passes.

#### Task 2: Group helpers in `layer_manager.py`
- **Estimate:** ~45 lines (incl. tests)
- **Files:** `rana_qgis_plugin/layer_management/layer_manager.py`, `tests/test_layer_manager.py`
- **Description:** Add `find_schematisation_group(db_filepath)` (normalized path match on `rana/schematisation_db_filepath`, `None` if not found) and `attach_revision_number_update(group, task)` (set `rana/revision_number` on `upload_succeeded`).
- **Depends on:** None
- **Acceptance:** Helpers exist in `layer_manager.py` and work against a real `QgsLayerTree`.
- **Evidence:** Unit tests: match with differently normalized paths, no match returns `None`, revision number updated on `upload_succeeded`.

### Core Implementation

#### Task 3: Split `save_revision` into the shared core and `commit_opened_revision`
- **Estimate:** ~80 lines (incl. tests)
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/layer_management/layer_tree_menu.py`, `rana_qgis_plugin/utils/qgis.py`, `tests/loader/test_schematisation.py`
- **Description:** Remove the unsaved-edits prompt and the "not loaded in editor" warning from `save_revision`. Add `commit_opened_revision(group, parent)`: read group properties, lock check, unsaved-edits prompt (keeping `bar_error` + stop on save failure and on `OSError` / `ValueError`), `save_revision`, `attach_revision_number_update`. `layer_tree_menu.save_revision` calls it. Delete `is_loaded_in_schematisation_editor`.
- **Depends on:** Tasks 1, 2
- **Acceptance:** Layer-panel "Save revision" behaves as before except no editor warning; prompt precedes the network fetch; errors while saving layer changes still stop the upload with a message.
- **Evidence:** `test_save_revision_requires_authenticated_api` passes unchanged; new tests: `commit_opened_revision` stops on "Cancel Upload", stops with `bar_error` when saving a layer fails, and stops before any prompt when locked; no remaining references to the deleted function.

#### Task 4: `Loader.commit_stored_revision`
- **Estimate:** ~110 lines (incl. tests)
- **Files:** `rana_qgis_plugin/loader.py`, `tests/loader/test_schematisation.py`
- **Description:** Resolve the schematisation id (`get_threedi_schematisation`), lock check, look up the local WIP (`None` DB path or `OSError` → no WIP), confirm with `wip_revision.main_dir`, find the open group, then call `commit_opened_revision(group, parent)` or `save_revision` with `wip_revision.number` and the DB path.
- **Depends on:** Tasks 1, 2, 3
- **Acceptance:** All failure cases in the design table produce the specified message and start nothing.
- **Evidence:** Unit tests for no auth, lookup failure, locked, no WIP, DB path `None`, `OSError` on lookup, user cancels, confirm to `save_revision`, open group to `commit_opened_revision`.

### Integration

#### Task 5: Context-menu action
- **Estimate:** ~30 lines (incl. tests)
- **Files:** `rana_qgis_plugin/data_items/file_actions.py`, `rana_qgis_plugin/data_items/file_item.py`, `tests/data_items/test_file_actions.py`
- **Description:** Add `FileAction.SAVE_LOCAL_REVISION` ("Save local revision", upload icon, no tooltip), include it for `threedi_schematisation` in `get_file_actions`, and wire it in `RanaFileDataItem.actions` to `commit_stored_revision`.
- **Depends on:** Task 4
- **Acceptance:** Action appears only for `threedi_schematisation` items; no API or disk access during menu construction.
- **Evidence:** Updated parametrized `test_get_file_actions` passes.

## Notes

- Commit after each task; unit tests and pre-commit hooks must pass. No E2E tests without explicit permission.
- Tests run in Docker (`docker compose run --rm qgis pytest -v tests`).
- Open at implementation: no-WIP wording.
- Deferred: uploading a stored (non-WIP) local revision; hiding/disabling the file action by local state; locking `save_initial_revision`.
- Manual test paths are listed in `design.md`.

## Progress

- [x] Task 1: Loader upload lock replaces the group lock
- [x] Task 2: Group helpers in `layer_manager.py`
- [x] Task 3: Split `save_revision` into the shared core and `commit_opened_revision`
- [x] Task 4: `Loader.commit_stored_revision`
- [ ] Task 5: Context-menu action
