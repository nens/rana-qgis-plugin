---
feature: fix_543_new_revision_status_bars
status: planned
created: 2026-11-24
decisions:
  - 20261124-1000-revision-upload-pre-dialog-bars
  - 20261124-1010-revision-upload-post-dialog-progress
  - 20261124-1020-progress-helpers-in-communication
---

# New Revision Status Bars Design

## Overview

Creating a new revision from the layer panel (`commit_opened_revision`) or the
Browser item (`commit_stored_revision`) runs through `Loader.save_revision` and
leaves many message-bar items behind. The cause is the same as the one fixed
for new schematisations in f977fda: each upload progress tick pushes a new
bar, and several paths push extra items or never remove them.

The flow has three phases. Only the message-bar items of the first and last
phase are in scope:

1. **Pre-dialog**: optional layer save, API fetch. A busy bar shows until the
   `UploadWizard` appears.
2. **In-dialog**: `UploadWizard`. Out of scope.
3. **Post-dialog**: `SchematisationUploadTask`. One progress item, updated in
   place, always removed, followed by one honest final message.

## User Stories

- As a user creating a revision, I want one progress item instead of a stack
  of bars.
- As a user waiting for the upload dialog, I want to see that something is
  being prepared.
- As a user whose revision fails the model checker, I want to know the
  revision was uploaded but no model was created, without a stale bar
  suggesting otherwise.
- As a user whose upload requests a model, I want to be pointed to the
  Processes panel, as when creating a schematisation.

## Root Cause

| Phase | Location | Problem |
|---|---|---|
| Pre | `loader.py` `save_revision` "preparing for save revision" | Does not paint (synchronous fetch); only removed on wizard cancel |
| Pre | `loader.py` `commit_opened_revision` "Save changed layers" | One bar per layer, then `clear_message_bar()` removes unrelated items |
| Post | `save_revision` `progress_changed` handler | `progress_bar()` per tick → new item per tick, never removed |
| Post | `taskCompleted` / `start_model_tracker_process` | Two extra info items |
| Post | `taskTerminated` | Error dialog only; bars stay. "MAKE MODEL" label remains after a model-checker failure |

## Components

### Progress helpers (`communication.py`)

See `../../knowledge/decisions/20261124-1020-progress-helpers-in-communication.md`.

- `update_progress(pb, value, detail=None)`
- `update_step_progress(pb, step, step_pct, detail=None)` (delegates)
- `finish_progress(iface, pb)` (was `finish_step_progress`)

Moved from `SchematisationWizardBase`; the wizard, `loader.py` and tests are
updated. Behaviour for `None` and dismissed (`sip.isdeleted`) bars is
unchanged.

### Pre-dialog bars (`loader.py`)

See `../../knowledge/decisions/20261124-1000-revision-upload-pre-dialog-bars.md`.

- `commit_opened_revision`: one "Saving layer changes" busy bar around the
  save loop, removed with `finish_progress` on success and failure. The
  `clear_message_bar()` call is removed.
- `save_revision`: one "Preparing revision upload" busy bar, followed by
  `QCoreApplication.processEvents()` so it paints before the synchronous
  fetch. Removed with `finish_progress` before `upload.exec()` and on every
  early return (auth, fetch error, missing organisation, `OSError`/`ValueError`).
  The `clear_message_bar()` on wizard cancel is removed.

### Post-dialog progress item (`loader.py`)

See `../../knowledge/decisions/20261124-1010-revision-upload-post-dialog-progress.md`.

Inside `save_revision`, after the wizard is accepted, following the closure
pattern of `build_initial_revision_task`:

- Create one bar with `progress_bar("Uploading revision", 0, 100, 0)`.
- `progress_changed(name, current, total, per_task)` →
  `update_progress(pb, total + current * per_task / 100, detail=<label>)`
  unless `handed_off`. Label maps task names to user text; at least
  `MAKE MODEL` → "Waiting for model checker". Other names keep the existing
  "Uploading revision: <name>" form unless a nicer label is obvious.
- `revision_committed(number)` → remember that the revision was committed.
- `model_requested` → `handed_off = True`; label "Starting model creation";
  `start_model_tracker_process(...)`; `finish_progress`; if a job id was
  returned, resolve the project (given dict, or `get_tenant_project(project_id)`)
  and call `point_user_to_processes` with
  "Track model creation for <name> in the Processes window?". If the project
  cannot be resolved, show one info message pointing to the Processes panel.
- `upload_succeeded(number)` without hand-off → `finish_progress`;
  `bar_info("Revision <N> uploaded.")`.
- `taskTerminated` → `finish_progress`; cancelled → `bar_warn`; committed →
  error "Revision <N> was uploaded, but no model was created: <error>";
  otherwise error "Revision upload failed: <error>".
- Upload-lock release (`_revision_uploads_in_progress.discard`) is unchanged.

`start_model_tracker_process` no longer pushes its "model creation started"
info message (affects the new-schematisation flow too).

### Plumbing

- `save_revision(project_id, schematisation_id, revision_number,
  schematisation_db_filepath, parent, error_signals, project=None)`.
- `commit_opened_revision(group, parent, error_signals)`.
- `commit_stored_revision(project, file_item, descriptor_id, parent,
  error_signals)`: passes `project` on to `save_revision` and
  `commit_opened_revision` handover.
- `FileItem` passes `self.error_signals`.
- `LayerTreeMenuProvider.__init__` gets `error_signals`; `rana_qgis_plugin.py`
  passes `self.error_signals`.

## Acceptance Criteria

- Both entry points show at most one Rana message-bar item at a time during a
  revision upload: a busy bar before the dialog, a progress bar after.
- No bar remains after success, cancellation, model-checker failure or any
  other failure.
- Model-checker failure reports that the revision was uploaded but no model
  was created.
- When a model is requested, the user is asked to track it in the Processes
  panel (both entry points).
- Without model creation, success ends with one "Revision <N> uploaded." info.
- Unrelated message-bar items are not cleared by this flow.
- The new-schematisation flow behaves as before, minus the redundant
  "model creation started" info item.

## Testing

Unit tests (real `QgsMessageBar` where feasible, as in the existing helper
tests):

- `update_progress` / `finish_progress` in their new location.
- `save_revision` wiring: progress ticks update one item; each terminal path
  removes it and emits the right message (cancel, failure before commit,
  failure after commit, success without model, model hand-off).
- Pre-dialog bar is removed on early returns and before the wizard opens.

## Manual Testing

- Layer panel → save revision, with and without unsaved edits, with and
  without "make 3Di model".
- Browser item → upload local revision, same variations, also with the WIP
  open in QGIS (handover to the layer path).
- A revision that fails the model checker: no stale bar, error says revision
  uploaded but no model created.
- Cancel the upload task from the QGIS task manager.
- Cancel the `UploadWizard`: busy bar is gone.
- Regression: create a new schematisation (from scratch and from file).

## Out of Scope

- Message-bar items pushed from inside `UploadWizard` (checks, migration).
- General `clear_msg_bar` behaviour of other callers.

## Open Questions

- Whether `revision_committed` (queued from the task thread) reliably arrives
  before `taskTerminated`; otherwise expose a committed flag on the task.
- Exact labels for the other upload step names.
