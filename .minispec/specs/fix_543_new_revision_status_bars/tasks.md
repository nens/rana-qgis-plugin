---
feature: fix_543_new_revision_status_bars
status: planned
created: 2026-11-24
chunk_size: adaptive
total_tasks: 5
estimated_lines: 450
---

# New Revision Status Bars Tasks

## Overview

Implements `design.md`: one busy bar before the `UploadWizard`, one in-place
progress item after it, always removed, with an honest final message and the
Processes-panel hand-off for model creation. Tests are bundled with each task.

## Task List

### Foundation

#### Task 1: Move progress helpers to communication.py
- **Estimate:** ~50 lines code + ~30 lines test moves
- **Files:** `rana_qgis_plugin/communication.py`,
  `rana_qgis_plugin/widgets/schematisation_new_wizard.py`,
  `rana_qgis_plugin/loader.py`, `tests/test_communication.py` (new),
  `tests/widgets/test_schematisation_new_wizard.py`,
  `tests/loader/test_initial_revision_upload.py`
- **Description:** Add module-level `update_progress(pb, value, detail=None)`
  (body of current `update_step_progress`: `None`/`sip.isdeleted` handling,
  label via `QTextBrowser` of `pb.parentWidget()`). Move
  `update_step_progress` (delegates to `update_progress`) and
  `finish_step_progress` → `finish_progress(iface, pb)`. Remove the static
  methods from `SchematisationWizardBase`; update all callers. Move helper
  tests to `tests/test_communication.py`; update patches in
  `test_initial_revision_upload.py`.
- **Depends on:** None
- **Acceptance:** No references to `SchematisationWizardBase.update_step_progress`
  / `finish_step_progress` remain (`grep`); new-schematisation behaviour
  unchanged.
- **Evidence:** Unit tests pass (`tests/test_communication.py`,
  `tests/widgets`, `tests/loader`).

### Core Implementation

#### Task 2: Pre-dialog bars
- **Estimate:** ~30 lines code + ~50 lines tests
- **Files:** `rana_qgis_plugin/loader.py`, `tests/loader/test_schematisation.py`
- **Description:**
  - `commit_opened_revision`: one "Saving layer changes" busy bar created
    before the save loop (not per layer); `finish_progress` on success and on
    every failure; remove `clear_message_bar()`.
  - `save_revision`: "Preparing revision upload" busy bar, then
    `QCoreApplication.processEvents()`; `finish_progress` before
    `upload.exec()` and on each early return (no API, fetch error, missing
    organisation, `OSError`/`ValueError`); remove `clear_message_bar()` on
    wizard cancel.
- **Depends on:** Task 1
- **Acceptance:** Pre-dialog bar is gone before the wizard opens and after
  each early return; unrelated message-bar items are not cleared.
- **Evidence:** Unit tests for early returns and wizard-cancel assert the bar
  item is removed and `clear_message_bar` is not called; existing
  `commit_opened_revision` tests pass.

#### Task 3: Post-dialog progress item
- **Estimate:** ~60 lines code + ~90 lines tests
- **Files:** `rana_qgis_plugin/loader.py`, `tests/loader/test_schematisation.py`
  (or new `tests/loader/test_revision_upload.py`)
- **Description:** Extract task wiring from `save_revision` into
  `Loader.wire_revision_upload(task, ...)`:
  - one bar `progress_bar("Uploading revision", 0, 100, 0)`;
  - `progress_changed` → `update_progress(pb, total + current * per_task / 100,
    detail=label)` unless `handed_off`; label maps `MAKE MODEL` →
    "Waiting for model checker", others "Uploading revision: <name>";
  - `revision_committed` → remember committed revision number;
  - `model_requested` → `handed_off = True`, label "Starting model
    creation", `start_model_tracker_process(...)`, `finish_progress`
    (interim: one info message; replaced in Task 4);
  - `upload_succeeded` without hand-off → `finish_progress`,
    `bar_info("Revision <N> uploaded.")`; drop the old `taskCompleted`
    info;
  - `taskTerminated` → `finish_progress`; cancelled → `bar_warn`; committed →
    error "Revision <N> was uploaded, but no model was created: <error>";
    otherwise "Revision upload failed: <error>";
  - keep the `_revision_uploads_in_progress` discard.
- **Depends on:** Task 1 (do after Task 2: both edit `save_revision`)
- **Acceptance:** Many progress ticks update one item; every terminal path
  removes it and emits exactly one final message; model-checker failure after
  commit reports "uploaded, but no model was created".
- **Evidence:** Unit tests per terminal path, including
  `revision_committed` followed by `taskTerminated` (ordering assumption) and
  ticks after hand-off being ignored.

#### Task 4: Model hand-off to Processes + plumbing
- **Estimate:** ~50 lines code + ~60 lines tests
- **Files:** `rana_qgis_plugin/loader.py`,
  `rana_qgis_plugin/data_items/file_item.py`,
  `rana_qgis_plugin/layer_management/layer_tree_menu.py`,
  `rana_qgis_plugin/rana_qgis_plugin.py`, `tests/loader/test_schematisation.py`,
  `tests/data_items/…`, `tests/layer_management/…` (as affected)
- **Description:**
  - `save_revision(..., error_signals, project=None)`,
    `commit_opened_revision(group, parent, error_signals, project=None)`,
    `commit_stored_revision(project, file_item, descriptor_id, parent,
    error_signals)` (passes `project` to both `save_revision` and the
    handover to `commit_opened_revision`).
  - `FileItem` passes `self.error_signals`; `LayerTreeMenuProvider` receives
    `error_signals` in `__init__` from `rana_qgis_plugin.py`.
  - In the `model_requested` handler: if a job id was returned, use the given
    project or `get_tenant_project(project_id)` (on `RanaFetchError` /
    `NetworkUnavailableError` fall back to one info message pointing to the
    Processes panel), then `point_user_to_processes(project, [job_id],
    error_signals, mainWindow, question="Track model creation for <name> in
    the Processes window?")`.
  - Remove `bar_info("Revision uploaded; model creation started.")` from
    `start_model_tracker_process`.
- **Depends on:** Task 3
- **Acceptance:** Both entry points end a model upload with the Processes
  prompt; project only fetched when no dict was given; new-schematisation
  flow loses only the redundant info.
- **Evidence:** Unit tests: hand-off with given project (no fetch), with
  fetched project, fetch failure fallback, no job id; existing
  `test_initial_revision_upload.py` and data-item/menu tests pass.

### Polish

#### Task 5: Docs
- **Estimate:** ~25 lines
- **Files:** `doc/schematisation_wizard.md`, `doc/layer_management.md`
- **Description:** Update helper references (`communication.update_step_progress`,
  `finish_progress`); describe revision-upload message-bar behaviour
  (pre-dialog busy bar, single progress item, final messages, Processes
  hand-off).
- **Depends on:** Task 4
- **Acceptance:** No stale references to `SchematisationWizardBase` helpers in
  `doc/`.
- **Evidence:** `grep -rn "finish_step_progress\|SchematisationWizardBase.update_step_progress" doc/` is empty.

## Notes

- Open question "revision_committed before taskTerminated" resolved by
  assumption: both are queued to the main thread in emission order;
  `revision_committed` is emitted during the commit step, long before the task
  ends. Covered by a test in Task 3.
- `UploadWizard` in-dialog message-bar items are out of scope.
- Manual testing paths are listed in `design.md`.

## Progress
- [ ] Task 1: Move progress helpers to communication.py
- [ ] Task 2: Pre-dialog bars
- [ ] Task 3: Post-dialog progress item
- [ ] Task 4: Model hand-off to Processes + plumbing
- [ ] Task 5: Docs
