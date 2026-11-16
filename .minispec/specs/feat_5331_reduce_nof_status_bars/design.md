---
feature: feat_5331_reduce_nof_status_bars
status: planned
created: 2026-11-16
decisions:
  - 20261116-1200-schematisation-step-progress
---

# Schematisation Creation Step Progress Design

## Overview

Replace the multiple progress and informational message-bar items produced by
the two schematisation creation workflows with one overall progress item. The
item will show the existing workflow stages and advance through three equally
weighted stages: local preparation, initial revision upload, and starting the
remote model-creation process.

This feature is limited to creating a schematisation from scratch and creating
one from an existing file. It does not change the general behavior of
`clear_msg_bar=False` for other operations.

## User Stories

- As a user creating a schematisation from scratch, I want one progress item
  that shows how far creation has progressed instead of several bars.
- As a user uploading an existing schematisation, I want the preparation and
  upload progress to appear in the same overall progress item.
- As a user waiting for model creation, I want to know when the remote model
  process has started and where to follow it in the Processes panel.

## Workflow Model

The overall progress range is divided into three equal segments:

1. **Local preparation**: 0–33%. This includes the existing wizard work,
   schema upgrade, file preparation, and local population/copying. Where the
   schema upgrade reports a percentage, that percentage is mapped into this
   segment and retained in the label. Work without measurable progress holds
   the segment until it completes.
2. **Initial revision upload**: 33–66%. Existing upload-task progress is
   mapped into this segment. The current upload detail text remains available
   in the label.
3. **Remote model hand-off**: 66–100%. The segment completes when the request
   to start the remote model-creation process succeeds. The remote process's
   internal progress is not represented by the local bar.

The progress item is updated in place: the same progress bar returned by
`progress_bar()` is passed along the workflow and updated for each callback.
It is not a new message-bar item for every progress callback. The label should
identify the current existing step and may include detail such as the
schema-upgrade percentage or upload task name.

## Components

### Step progress helper functions

Plain module-level functions in `rana_qgis_plugin/communication.py`, next to
`progress_bar()`. No new class and no state held between calls:

- `step_overall_value(step, step_pct)`: maps a 0-based step and a step-local
  percentage to the overall 0–100 value (three equal segments).
- `update_step_progress(pb, step, step_pct, detail=None)`: sets the bar value
  and, when a detail is given, the label text. The label is found from the bar's
  parent message widget (`pb.parentWidget()`), so `progress_bar()` does not
  need to change.
- `finish_step_progress(iface, pb)`: removes the message-bar item that holds
  `pb` (`popWidget(pb.parentWidget())`) so the operation leaves no stale
  progress UI behind. Failure and cancellation paths call it, then report the
  existing warning or error.

These functions do not alter unrelated message-bar items or the behavior of
other callers. A stateful progress object that owns the item and step is a
possible future refactor of the communication class, out of scope here.

### Schematisation wizard integration

Create the progress bar once per creation operation with `progress_bar()` and
pass it through both wizard paths. Replace the current schema-upgrade progress
callback with `update_step_progress` for the local-preparation segment.
Preparation operations that do not report progress set that segment complete
when they finish.

Remove intermediate success notifications from the wizard that would create a
second message-bar item for the same operation.

### Upload task integration

Map `SchematisationUploadTask.progress_changed` into the revision-upload
segment rather than creating a separate progress item for each callback.
When upload work requests model creation, call `update_step_progress` for the
remote-model hand-off segment (step 2).

### Remote process notification

Retain the existing notification that model creation has started and directs
the user to the Processes panel. It is the final hand-off status, not progress
for the remote process. Upload completion handling must not immediately clear
or replace this notification with a misleading local-upload-only success
message.

## Acceptance Criteria

- From-scratch creation displays one progress item throughout local
  preparation, upload, and model hand-off.
- Existing-file creation displays one progress item throughout the same three
  stages.
- The overall progress advances through three equal portions.
- Schema-upgrade percentages are visible in the preparation label and are
  mapped into the first third of the overall bar.
- Upload-task progress and task detail are mapped into the second third.
- The bar reaches completion when the remote model process is successfully
  started; no local percentage is claimed for remote model creation.
- Existing process-tracking guidance remains visible after the hand-off.
- Cancellation and failure report the appropriate existing warning/error and
  do not leave a stale progress item.
- Other progress-bar callers, including save-revision and download flows, are
  unchanged by this feature.

## Manual Testing

- Complete a from-scratch creation and verify the preparation, upload, and
  model hand-off stages in one message-bar item.
- Complete an existing-file creation and verify the same behavior.
- Use a schema upgrade that reports progress and confirm the percentage is
  shown in the label while the bar remains within the first third.
- Verify a successful hand-off leaves the Processes-panel guidance visible.
- Cancel or fail each flow and verify that the final warning/error is shown
  without a stale progress bar.

## Open Questions

- Exact user-facing wording can follow the existing messages; implementation
  should avoid introducing new workflow terminology.
- The existing communication test strategy should determine whether the
  helper can be tested with a lightweight real Qt/QGIS message-bar fixture.
