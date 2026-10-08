---
feature: feat_452_open_schema
status: complete
created: 2026-08-31
chunk_size: adaptive
total_tasks: 11
estimated_lines: 620
---

# Open Schematisation and Save Revision Tasks

## Overview

Implements `.minispec/specs/feat_452_open_schema/design.md`. Tasks are ordered
as vertical slices: each one leaves the plugin in a state that can be manually
tested end-to-end before moving to the next, with a narrow, specific manual
test scope.

**Current status: implementing.** The QGIS 4-compatible threedi schematisation
editor is available, so implementation and end-to-end manual testing can
continue.

**Legacy import policy:** new code must not import from `rana_qgis_plugin.legacy`.
Rather than cherry-picking individual functions out of legacy piece by piece,
the entire `legacy/simulation/` package has already been relocated wholesale to
`rana_qgis_plugin/simulation/` (merged with the existing `simulation/threedi_calls.py`
module) as preparatory work for this feature — see "Legacy Move (already done)"
below. This preserves the package's existing internal structure (`upload_wizard/`,
`load_schematisation/`, `data_models/`, etc.) instead of reorganizing it into
new `utils/`/`dialogs/` modules, since most of it will also be reused by later
simulation-related features. Internal imports *within* `legacy/` that pointed at
`legacy.simulation.*` (in `legacy/loader.py` and a few `legacy/widgets/*` files)
were left as-is and will now fail if exercised — that's expected and acceptable;
those files aren't imported by any active code path today (confirmed by
grep) and legacy code is never required to keep working per `AGENTS.md`.

## Legacy Move (already done)

- `rana_qgis_plugin/legacy/simulation/` moved to `rana_qgis_plugin/simulation/`
  in full, preserving its internal folder structure and relative imports
  (`custom_items.py`, `data_models/`, `initial_concentrations.py`,
  `load_schematisation/`, `model_selection.py`, `simulation_init.py`,
  `simulation_wizard.py` + `simulation_wizard/`, `substance_concentrations.py`,
  `upload_wizard/`, `utils.py`, `utils_ui.py`, `workers.py`). Merged cleanly
  with the pre-existing `rana_qgis_plugin/simulation/threedi_calls.py` (empty
  `__init__.py` on both sides, no collision).
- Updated the two active-code call sites that referenced the old path:
  `rana_qgis_plugin/layer_management/layer_manager.py` and
  `rana_qgis_plugin/workers/download.py` now import from
  `rana_qgis_plugin.simulation.utils` instead of
  `rana_qgis_plugin.legacy.simulation.utils`.
- Fixed one self-reference inside the moved code that still pointed at the old
  legacy path (`rana_qgis_plugin/simulation/upload_wizard/upload_wizard.py` was
  importing `LogLevels`/`TreeViewLogger` from
  `rana_qgis_plugin.legacy.simulation.utils`; now imported via the existing
  relative `from ..utils import (...)` in the same file, since those names live
  in the now-co-located `utils.py`).
- Verified: no file under `rana_qgis_plugin/simulation/` imports anything from
  `rana_qgis_plugin.legacy` anymore; all moved files still parse.
- Not moved: `legacy/simulation/upload_wizard/model_deletion.py` is a **copy
  that stayed too** (it's part of `upload_wizard/`, which moved wholesale) —
  it is available at `rana_qgis_plugin/simulation/upload_wizard/model_deletion.py`
  and can be used once "make 3Di model on upload" is in scope (Task 8 still
  defers actually wiring it up, see below).

Everything the remaining tasks need — `resolve_schematisation_download_dir`,
`download_required_files`, `resolve_schematisation_download_dir_auto`,
`SchematisationLoad`, `UploadWizard`, `ModelDeletionDialog`,
`SchematisationUploadProgressWorker`, and their shared enums/helpers
(`UploadFileStatus`, `FileState`, `SchematisationRasterReferences`,
`zip_into_archive`, etc.) — now lives under `rana_qgis_plugin/simulation/`,
so the tasks below reference that package directly instead of describing
individual relocations.

## Type-checking (already done)

Moving code out of `legacy/` also moves it out from under `mypy.ini`'s
`exclude = rana_qgis_plugin/legacy/.*` and the blanket
`[mypy-rana_qgis_plugin.legacy.*] ignore_errors = True`, so mypy started
checking it for the first time and surfaced ~335 pre-existing errors across
the moved package. Rather than leaving all of it exempted or fixing
everything speculatively:

- `utils.py`, `utils_ui.py`, `load_schematisation/schematisation_load_local.py`,
  and `upload_wizard/upload_wizard.py` — the four files this feature's tasks
  actually use — have been fixed and are now fully mypy-clean (no
  `ignore_errors` entry for them in `mypy.ini`). Fixes were small and
  mechanical: a stray duplicate function definition, a few `assert`s to help
  mypy narrow attributes it couldn't otherwise correlate, one dict type
  annotation, swapping a private `WarningMessage._category_name` for the
  public `warning.category.__name__`, `# type: ignore[misc,valid-type]` on
  the `uic.loadUiType()`-derived dialog base classes (a well-known, safe
  pattern for that construct), one `defaultdict[str, Any]` annotation, and
  fixing a QGIS-4/Qt6 API mismatch (`Qgis.Warning` → `Qgis.MessageLevel.Warning`).
- The remaining 8 modules this feature doesn't touch (`workers.py`,
  `simulation_wizard.py`, `data_models/simulation_data_models.py`,
  `substance_concentrations.py`, `initial_concentrations.py`,
  `simulation_init.py`, `model_selection.py`,
  `upload_wizard/model_deletion.py`) still carry an explicit per-module
  `ignore_errors = True` in `mypy.ini`, each with a comment explaining why —
  remove each entry once a future task actually adapts that file.
- `pre-commit` (`ruff-check`, `ruff-format`, `mypy` with the real
  `qgis-stubs`/`PyQt6-stubs`) passes on all four fixed files.

**Consequence for Task 7:** it's the one remaining task that touches a
currently-exempted file (`workers.py`, 107 of the ~335 errors, mostly the
`self.tc: Optional[ThreediCalls]` access-without-narrowing pattern). Since
Task 7 already rewrites that file's threading wrapper, fixing its mypy errors
and removing its `mypy.ini` entry is folded into that task's acceptance
criteria below rather than treated as separate follow-up work.

## Task List

### Foundation

#### Task 1: Add schematisation open entry points (menu, double-click, multi-select)
- **Estimate:** ~70 lines
- **Files:** `rana_qgis_plugin/utils/data_models.py`, `rana_qgis_plugin/data_items/file_item.py`, `rana_qgis_plugin/data_items/gui_provider.py`, `rana_qgis_plugin/loader.py`
- **Description:**
  - Add `OpenSchematisationRequest` to `data_models.py` (project, file_item), parallel to `OpenFileRequest`.
  - Widen the `("vector", "raster")` filters in `file_item.py:handleDoubleClick`, `gui_provider.py:open_selected_items`, and `loader.py:resolve_folder` to also match `threedi_schematisation`, producing an `OpenSchematisationRequest` instead of `OpenFileRequest` for that data type.
  - In `Loader.open_items()`, route `OpenSchematisationRequest`s into a new (temporarily stubbed) branch — e.g. logs/shows a message-bar note with the resolved project + file id — so the wiring can be verified without any download/resolution logic yet.
- **Depends on:** None
- **Acceptance:** Triggering "Open in QGIS" via context menu, double-click, multi-select (mixed with raster/vector), or folder-select on a schematisation reaches the stub without error, and does not affect existing raster/vector open behavior.
- **Evidence:** Manual test — each of the four trigger paths on a schematisation logs/shows the expected stub message; existing raster/vector open paths still work unchanged.

#### Task 2: Resolve schematisation download location and WIP decision
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/loader.py`
- **Uses (already moved, no further relocation needed):** `resolve_schematisation_download_dir()` (`rana_qgis_plugin/simulation/utils.py:662`, interactive Replace/Store/Cancel, main-thread only).
- **Description:** Implement (without wiring to any UI trigger yet) the resolution step for a given project + schematisation file item: fetch schematisation + latest revision via `get_threedi_schematisation(descriptor_id)`, then resolve the local download directory using `hcc_working_dir()` (`utils/settings.py`) and `resolve_schematisation_download_dir`. This is the decision that actually determines where files land: if a local WIP differs from the requested revision, prompt Replace WIP / Store as separate revision / Cancel — matching the accepted "keep the logic for choosing whether that will replace the existing revision or create a new WIP" decision. Returns everything needed to construct a `SchematisationRevisionDownloadContext`/`SchematisationRevisionDownloader` (schematisation dict, revision dict, local_schematisation, wip_replace_requested, target dir), or a clear "cancelled" result if the user declines.
- **Depends on:** None (can be built/tested in parallel with Task 1)
- **Acceptance:** Given a schematisation file item, the resolution function returns correct schematisation/revision metadata and a valid, writable local directory consistent with `hcc_working_dir()`; the Replace/Store/Cancel dialog appears only when a conflicting local WIP exists, and Cancel is honored (no download proceeds).
- **Evidence:** Unit test with a mocked `get_threedi_schematisation` API response and a mocked dialog choice, asserting the returned local dir/WIP decision for each branch (no local schematisation, matching WIP, conflicting WIP + Replace, conflicting WIP + Store, conflicting WIP + Cancel); no manual QGIS test needed yet since it isn't wired to a trigger.

#### Task 3: Download and open the schematisation end-to-end
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/loader.py`
- **Description:** Replace the Task 1 stub with real behavior: use Task 2's resolution to construct `SchematisationRevisionDownloadContext` + `SchematisationRevisionDownloader` (which already calls `download_required_files()` from `rana_qgis_plugin.simulation.utils`), register it with the existing `DownloadTask` pipeline (same de-duplication/confirmation/error-reporting used for raster/vector), and add a download-finished callback that calls `LayerManager.add_from_schematisation(...)` with the resolved local schematisation, revision number, and geopackage path.
- **Depends on:** Task 1, Task 2
- **Acceptance:** Opening a schematisation via any of the four trigger paths downloads the latest revision (running the Replace/Store/Cancel dialog when applicable) and opens it in the schematisation editor; cancelling that dialog leaves nothing downloaded/opened.
- **Evidence:** Manual test — each of the four trigger paths (context menu, double-click, multi-select, folder-select) on a schematisation opens it successfully end-to-end; repeat with an existing local WIP to confirm the Replace/Store/Cancel prompt behaves correctly.

#### Task 4: Tag the loaded schematisation group with Rana identity
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/layer_management/layer_manager.py`, `rana_qgis_plugin/loader.py`
- **Description:** After `add_from_schematisation` creates the top-level layer group for the loaded geopackage, set custom properties identifying it (`rana/schematisation_id`, `rana/revision_number`, plus existing `rana/project_id`/path conventions) so it can be found later by the layer-tree menu provider. Extend `RanaLayerRef`-style helpers or add a small dedicated helper rather than duplicating property-key logic.
- **Depends on:** Task 3
- **Acceptance:** After opening a schematisation, its top-level layer group carries the expected custom properties with correct values.
- **Evidence:** Unit test on the tagging helper (property keys/values set correctly given known inputs); manual check via QGIS Python console (`group.customProperty("rana/schematisation_id")`) after opening.

### Core Implementation

#### Task 5: Add "Save revision" menu action (stub handler)
- **Estimate:** ~50 lines
- **Files:** `rana_qgis_plugin/layer_management/layer_tree_menu.py`
- **Description:** Extend `LayerTreeMenuProvider.on_context_menu()` to detect a `QgsLayerTreeGroup` tagged with `rana/schematisation_id` (Task 4) and append a "Save revision" action, always enabled per the design decision (no edit-state tracking). Wire it to a handler method that is a clear, narrow stub for now (e.g. logs/shows an info message bar "Save revision not yet implemented") so the menu item's visibility and targeting logic can be verified independently of the upload implementation.
- **Depends on:** Task 4
- **Acceptance:** "Save revision" appears only on schematisation groups (not on raster/vector Rana groups or unrelated groups), and clicking it triggers the stub without error.
- **Evidence:** Manual test — right-click a schematisation group vs. a raster/vector group vs. a plain group; confirm the action's presence/absence matches expectations.

#### Task 6: Resolve upload source and confirm before upload
- **Estimate:** ~90 lines
- **Files:** `rana_qgis_plugin/layer_management/layer_tree_menu.py` or a new `rana_qgis_plugin/loader.py` method
- **Uses (already moved, no relocation needed):** `SchematisationLoad` dialog (`rana_qgis_plugin/simulation/load_schematisation/schematisation_load_local.py`), `UploadWizard` (`rana_qgis_plugin/simulation/upload_wizard/upload_wizard.py`), `get_editable_layers_for_file`/`save_layer_changes` (`utils/generic.py:228,261`), `is_loaded_in_schematisation_editor` (`utils/qgis.py:29`).
- **Defer:** `ModelDeletionDialog` (`rana_qgis_plugin/simulation/upload_wizard/model_deletion.py`) is only reached when the upload's "make 3Di model" option is used. Skip wiring it in this task; if `new_upload["make_3di_model"]` is true, show a "not yet supported" message and stop.
- **Description:** Replace the Task 5 stub with the pre-upload logic ported from legacy `Loader.save_revision` (`legacy/loader.py:1653-1817`, reference only — control flow re-implemented against the new group-tagging model). This is distinct from Task 2's download-location decision (Replace WIP/Store/Cancel) — here we're deciding what to upload *from*, given the group's tagged schematisation/revision: if no local WIP exists, prompt the user to pick a stored local revision to upload (`SchematisationLoad` dialog); check for unsaved layer edits and prompt to save/discard (already-ported helpers); warn if the geopackage isn't currently loaded in the schematisation editor (already-ported helper); then open `UploadWizard` for final confirmation. This stays on the main thread (dialogs only) and stops short of performing the actual upload.
- **Depends on:** Task 5
- **Acceptance:** Clicking "Save revision" walks through the same decision points as legacy (no-WIP revision picker, unsaved-edit prompt, not-loaded-in-editor warning, wizard), ending in a confirmed "ready to upload" state (upload itself deferred to Task 7); choosing "make 3Di model" shows a clear "not yet supported" message instead of erroring.
- **Evidence:** Manual test — trigger with unsaved layer edits present and absent, and with/without an existing local WIP; confirm prompts appear/skip as expected.

#### Task 7: Perform the upload via a QgsTask
- **Estimate:** ~130 lines
- **Files:** `rana_qgis_plugin/workers/upload.py` (new), `rana_qgis_plugin/layer_management/layer_tree_menu.py` or `loader.py`
- **Uses (already moved, no relocation needed):** the per-step task-method bodies from `SchematisationUploadProgressWorker` (`rana_qgis_plugin/simulation/workers.py:1184-1469` — `build_tasks_list`, `create_revision_task`, `upload_sqlite_task`, `delete_sqlite_task`, `upload_raster_task`, `delete_raster_task`, `commit_revision_task`, `create_3di_model_task`, `report_upload_progress`, `monitor_upload_progress`), which are pure `ThreediCalls`/API logic with no threading primitives beyond emitting signals.
- **Description:** Implement a `SchematisationUploadTask(QgsTask)` that performs the network upload confirmed in Task 6, replacing legacy's `QRunnable`/`QThreadPool` + `UploadWorkerSignals` pattern (`rana_qgis_plugin/simulation/workers.py:1171,1184`). Carry the task-method bodies over largely unchanged; replace only the wrapper: use `self.isCanceled()` instead of a manually-set `upload_canceled` flag, and expose progress/finished/failed through QGIS task signals consistent with `DownloadTask`'s conventions. Keep all Qt/layer-tree mutations on the main thread via signal handlers. On success, update the group's `rana/revision_number` custom property (Task 4) to the new revision. Submit via `QgsApplication.taskManager()`. Defer `create_3di_model_task` (depends on the deferred `ModelDeletionDialog` from Task 6) unless `make_3di_model` support is added back later. While rewriting this file's wrapper, also resolve its ~107 pre-existing mypy errors (see "Type-checking (already done)" above — mostly `self.tc: Optional[ThreediCalls]` accessed without narrowing; a lazy `@property` for `tc`, or an early `assert`/non-optional constructor argument on the new `QgsTask`, removes most of them at once) and drop its `[mypy-rana_qgis_plugin.simulation.workers] ignore_errors = True` entry from `mypy.ini`.
- **Depends on:** Task 6
- **Acceptance:** Saving a schematisation with real edits produces a new revision on the server, updates the local group's tagged revision number, and reports progress/success without freezing the QGIS UI; `mypy` passes on the new module with no `ignore_errors` carve-out needed.
- **Evidence:** Manual test — edit a schematisation layer, save revision, confirm new revision appears via Rana/API and the group property updates; verify UI remains responsive during upload; verify a failed upload (e.g. simulate network error) surfaces a clear message-bar error and leaves the group in a consistent state. `pre-commit run mypy` passes.

### Integration & Polish

#### Task 10: Error handling and regression pass
- **Estimate:** ~80 lines
- **Files:** touch-ups across `loader.py`, `layer_management/layer_tree_menu.py`, `workers/download.py`/`workers/upload.py` as needed
- **Description:** Sweep both flows for edge cases not yet covered: invalid/missing schematisation metadata from the API, local revision directory unavailable or unwritable, upload conflicts (e.g. remote revision advanced since WIP was taken), and task cancellation mid-download/mid-upload. Ensure every failure path leaves no partially-registered layer group and reports via the existing `communication.py` message-bar/log utilities.
- **Depends on:** Tasks 1-9
- **Acceptance:** Each identified edge case produces a clear user-facing message and leaves QGIS in a consistent state (no orphaned groups, no silent failures).
- **Evidence:** Manual test pass through the edge-case list above; existing automated tests still pass.

#### Task 11: Verify legacy loose ends
- **Estimate:** ~10 lines (verification/grep, not code)
- **Files:** none expected; may touch `legacy/loader.py` or `legacy/widgets/*.py` only if something unexpectedly does import them at runtime
- **Description:** Confirm the assumption from the Legacy Move above still holds once all other tasks are done: nothing in the active plugin (outside `legacy/`) imports `legacy.loader` or `legacy.widgets`, so their now-broken `legacy.simulation.*` imports remain inert. Re-run the grep check; if anything active turns out to depend on them, address it as a follow-up (not blocking this feature).
- **Depends on:** Task 10
- **Acceptance:** `grep -rn "from rana_qgis_plugin.legacy" rana_qgis_plugin --include=*.py | grep -v '^rana_qgis_plugin/legacy/'` returns nothing.
- **Evidence:** Grep output attached to the PR description.

### Post-review follow-ups (PR #474)

#### Task 12: Fix subfolder layer-tree hierarchy for opened schematisations
- **Files:** `loader.py` (~line 1051-1055)
- **Description:** `on_downloaded`'s `parents` construction uses `PurePosixPath(request.file_item["id"]).parents[:-1]`, which is reverse-ordered and yields cumulative (not per-segment) path strings for nesting deeper than one level (e.g. `a/b/schema.gpkg` produces group names `"a/b"` then `"a"` instead of `"a"` then `"b"`). Replace with `PurePosixPath(request.file_item["id"]).parts[:-1]`.
- **Depends on:** none
- **Acceptance:** Opening a schematisation nested two or more folders deep produces correctly ordered, per-segment layer-tree groups matching the file's folder structure.
- **Evidence:** Manual test — open a schematisation file at a path with at least two folder levels (e.g. `a/b/schema.gpkg`) and confirm the layer tree shows nested groups `a` → `b`, not a reversed/malformed single group.

#### Task 13: Guard against missing 3Di API client in save_revision
- **Files:** `loader.py` (`save_revision`, ~line 131-160)
- **Description:** `ThreediCalls.__init__` (`simulation/threedi_calls.py:143-144`) stores `threedi_api` unchecked; if `get_threedi_api()` returns `None` (no personal API token configured), the first API call (e.g. `fetch_schematisation` → `self.threedi_api.schematisations_read(...)`) raises `AttributeError` on `NoneType`, which is not caught by the existing `except (RanaFetchError, NetworkUnavailableError)` clause — resulting in an unhandled traceback instead of a friendly message. Add an explicit `if api is None:` check (mirroring `resolve_schematisation`'s pattern at `loader.py:999-1004`) before constructing `ThreediCalls`, and show a clear `bar_error` prompting the user to configure their 3Di API token.
- **Depends on:** none
- **Acceptance:** Triggering "Save revision" with no 3Di personal API token configured shows a clear message-bar error instead of raising an unhandled exception.
- **Evidence:** Manual test — clear the 3Di personal API token in settings, trigger "Save revision" on a loaded schematisation, confirm a friendly error appears (no Python traceback/crash).

#### Task 14: Deduplicate bulk-open requests
- **Status:** Deferred to separate ticket; the actual issue is aggregating multiple selected layers from one file so the file is downloaded once.
- **Files:** `data_items/gui_provider.py` (`open_selected_items`), `loader.py` (`open_items`/`_resolve_folder`)
- **Description:** Multi-select "Open in QGIS" builds one request per selected tree item with no deduplication. Selecting a file together with one of its child layers, or a folder together with a file already inside it, produces two independent requests for the same `file_item["id"]` — resulting in redundant concurrent downloads of the same file. Add a dedup step (keyed on e.g. `(project_id, file_id)` for file/schematisation requests and `(file_id, layer_id)` for layer requests) before dispatch, ideally before the existing `len(resolved) > 50` check.
- **Depends on:** none
- **Acceptance:** Selecting overlapping items (file + its layer; folder + file inside it) results in exactly one download/open per underlying file (or file+layer combination), not duplicates.
- **Evidence:** Manual test — select a vector file and one of its layers together, and separately a folder plus a file inside it; confirm only one download occurs per case.

#### Task 15: Add missing unit test coverage for open/schematisation flows
- **Files:** `tests/test_loader_schematisation.py` (or new test modules as appropriate)
- **Description:** Current tests only cover invalid metadata and unwritable directories. Add tests for: successful schematisation dispatch/opening; correct subfolder parent/group construction (covering Task 12's fix, including 2+ level nesting); `save_revision` behavior when no 3Di API token is configured (covering Task 13's fix); and dedup behavior for overlapping bulk-open selections (covering Task 14's fix).
- **Depends on:** Tasks 12, 13, 14
- **Acceptance:** New tests fail without the corresponding fixes and pass with them; `pytest` passes overall.
- **Evidence:** Test run output attached to the PR description.

## Notes

- `resolve_schematisation_download_dir` (Task 2, interactive Replace/Store/Cancel) governs where an open downloads to and whether it clobbers a local WIP. Save revision uses the metadata recorded on the loaded group to identify its local source.
- Task 5's stub is deliberately real (visible in the UI, wired to a handler) rather than throwaway scaffolding — it narrows Task 6/7 review scope without leaving dead code.
- Deferred (see design.md Scope Boundaries): edit-state-aware enabling of "Save revision", browser indicators for unsaved changes, multi-schematisation batch save, "make 3Di model on upload".

## Progress

- [x] Legacy move: relocate `legacy/simulation/` to `simulation/` wholesale
- [x] Type-checking: fix mypy errors in `utils.py`, `utils_ui.py`, `load_schematisation/schematisation_load_local.py`, `upload_wizard/upload_wizard.py`; narrow `mypy.ini` carve-out to the 8 remaining untouched modules
- [x] Task 1: Add schematisation open entry points (menu, double-click, multi-select)
- [x] Task 2: Resolve schematisation download location and WIP decision
- [x] Task 3: Download and open the schematisation end-to-end
- [x] Task 4: Tag the loaded schematisation group with Rana identity
- [x] Task 5: Add "Save revision" menu action (stub handler)
- [x] Task 6: Resolve upload source and confirm before upload
- [x] Task 7: Perform the upload via a QgsTask
 - [x] Task 8: Defer upload preparation until after user confirmation and show preparation progress
- [x] Task 9: Lock schematisation editing and Save revision during upload
  - Save revision is disabled while an upload is active.
  - Layer edit/commit guards were investigated but could not be implemented reliably with QGIS 4.2 Python bindings; deferred.
  - Prevent entering edit mode for layers that were not already editing.
  - Block commits for layers already in edit mode.
  - Disable the group's **Save revision** action while an upload is active.
  - Restore all layer states and re-enable the action on success, failure, and cancellation.
- [x] Task 10: Error handling and regression pass
  - Item 4 (remote revision conflict detection) skipped by decision; existing upload behavior remains unchanged.
- [x] Task 11: Verify legacy loose ends
- [x] Task 12: Fix subfolder layer-tree hierarchy for opened schematisations
- [x] Task 13: Guard against missing 3Di API client in save_revision
- [x] Task 14: Deferred to separate ticket (aggregate multiple selected layers per file)
- [x] Task 15: Add missing unit test coverage for open/schematisation flows
