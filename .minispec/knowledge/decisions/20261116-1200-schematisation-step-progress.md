# Decision: Use one equal-segment step-progress item for schematisation creation

**Date**: 2026-11-16 12:00  
**Status**: Accepted  
**Feature**: `feat_5331_reduce_nof_status_bars`

## Context

Creating a schematisation from scratch or from an existing file currently
reports local preparation, upload progress, and model-start status through
separate message-bar updates. Users see too many status/progress items instead
of one coherent operation.

## Decision

Use one progress item in the QGIS message bar for each creation operation. The
item represents three existing workflow stages, each allocated one third of
the overall progress range:

1. local preparation;
2. initial revision upload; and
3. remote model-creation hand-off.

Existing stage-local percentages are mapped into the relevant third. Schema
upgrade progress is shown in the label as detail. Operations without a
percentage complete their segment when their work finishes. The third stage
completes when the remote model process is successfully started; the plugin
does not claim to track the remote process locally.

The existing guidance directing users to the Processes panel is retained. The
general `clear_msg_bar=False` behavior and unrelated progress callers are out
of scope.

## Rationale

The code already exposes progress for schema upgrade and revision upload, and
already signals when the remote model request is made. Mapping those signals
into equal ranges provides an honest overall indicator without estimating
durations or inventing progress for unmeasured preparation work. Keeping the
existing stages and messages avoids introducing new user-facing terminology.

## Consequences

- A communication-layer step-progress helper is needed for this workflow. It is
  implemented as plain functions (`step_overall_value`,
  `update_step_progress`, `finish_step_progress`) that take the progress bar
  returned by `progress_bar()`. A stateful reporter object was considered and
  deferred: it would add a new interface for two call sites, and could be
  revisited as part of a future refactor of the communication class.
- Preparation may pause visually during work that has no progress callback;
  this is preferable to reporting fabricated percentages.
- The remote model's later progress remains in the Processes panel.
- Other message-bar progress behavior is deliberately unchanged and may be
  addressed by a separate feature.
- The helpers were implemented on `SchematisationWizardBase`; they move to
  `communication.py` in `20261124-1020-progress-helpers-in-communication`.
