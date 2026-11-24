---
type: decision
id: 20261124-1010-revision-upload-post-dialog-progress
date: 2026-11-24
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/data_items/file_item.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
  - rana_qgis_plugin/rana_qgis_plugin.py
tags: [upload, save-revision, message-bar, progress, processes]
participants: [margriet, agent]
---

# Revision upload: one in-place progress item after the dialog, always closed

## Context

After `UploadWizard` is accepted, every `SchematisationUploadTask.progress_changed`
tick pushes a new message-bar item, and none is removed. Completion pushes two
more info items. On failure only an error dialog is shown and the bars remain.
When the model checker rejects a revision, the last bars read
"Uploading revision: MAKE MODEL", which suggests a model is being created,
although `model_requested` is never emitted. The revision itself was committed.

The new-schematisation flow fixed the same problem in f977fda
(`20261116-1200-schematisation-step-progress`).

## Options Considered

### Progress model

- **Single 0–100 bar from the task's own progress** (chosen): the task's step
  list already includes the model-checker wait, so no segments are invented.
- Reuse the three-step helper: the first third would be fake (the wizard is
  already done), the last third meaningless without a model.
- Generalise the step helper to n steps: more interface for no gain.

### Model hand-off

- **Ask to open the Processes panel** (chosen), as for new schematisations.
- Info message only: no plumbing, but inconsistent and no job highlighting.

### Project dict in the layer-panel path

- **Lazy fetch at hand-off** (chosen): `get_tenant_project(project_id)` only
  when a model was requested and no dict was given; on failure fall back to an
  info message.
- Fetch up front: an extra request and pre-dialog failure point on every upload.

## Decision

- One progress item is created when the upload task is submitted. Each
  `progress_changed` updates it in place: value = task overall progress, label
  = a friendly name for the current step (`MAKE MODEL` → "Waiting for model
  checker"). Ticks after hand-off are ignored.
- `model_requested`: label "Starting model creation", start the model tracker,
  remove the item, then `point_user_to_processes` with
  "Track model creation for <name> in the Processes window?". If the job id or
  project cannot be determined, show one info message pointing to the
  Processes panel.
- Completed without model: remove the item, one info "Revision <N> uploaded."
- Terminated: remove the item. Cancelled → warning. Failed after
  `revision_committed` → error "Revision <N> was uploaded, but no model was
  created: <error>". Failed before → error "Revision upload failed: <error>".
- `save_revision` gains `error_signals` and an optional `project` dict.
  `commit_stored_revision` passes both from `FileItem`; the plugin passes its
  `error_signals` to `LayerTreeMenuProvider` for `commit_opened_revision`.

## Consequences

- Every exit path removes exactly the item it created; no `clear_message_bar()`.
- Users can tell an uploaded revision without a model from a failed upload.
- Signatures of `save_revision`, `commit_opened_revision`,
  `commit_stored_revision` and `LayerTreeMenuProvider.__init__` change.
