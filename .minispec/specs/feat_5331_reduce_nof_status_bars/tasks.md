---
feature: feat_5331_reduce_nof_status_bars
status: planned
created: 2026-11-16
chunk_size: adaptive
total_tasks: 4
estimated_lines: 200
---

# Schematisation Creation Step Progress Tasks

## Overview

Show one equal-segment progress item in the QGIS message bar for the
from-scratch and upload-existing schematisation creation workflows. Existing
preparation, schema-upgrade, upload, and remote model hand-off signals are
mapped into one overall 0–100 range. General `clear_msg_bar=False` behavior and
unrelated progress callers are out of scope.

## Task List

### Foundation

#### Task 1: Implement the step-progress helper functions and tests
- **Estimate:** ~40–60 lines
- **Files:** `rana_qgis_plugin/communication.py`, `tests/test_communication.py`
- **Description:** Add plain module-level helpers next to `progress_bar()`:
  - `step_overall_value(step, step_pct)` maps a 0-based step and a step-local
    percentage to the overall 0–100 value (three equal segments).
  - `update_step_progress(pb, step, step_pct, detail=None)` sets the bar value
    and, when a detail is given, the label text of the message widget that
    holds `pb`.
  - `finish_step_progress(iface, pb)` removes the message-bar item that holds
    `pb`.
  `progress_bar()` and its existing callers are not changed. No stateful class.
- **Depends on:** None
- **Acceptance:** Step-local progress maps to 0–33, 33–66, and 66–100; the label
  is found from the bar alone; finishing removes only the item for that bar.
- **Evidence:** Unit tests cover the mapping at segment boundaries, label
  updates, and removal of the item.

### Core Implementation

#### Task 2: Integrate local-preparation progress into both wizards
- **Estimate:** ~50–70 lines
- **Files:** `rana_qgis_plugin/widgets/schematisation_new_wizard.py`,
  `tests/widgets/test_schematisation_new_wizard.py`
- **Description:** Create one progress bar via `progress_bar()` on both wizard
  paths and keep it in the wizard flow. Map schema-upgrade callbacks into the
  first third with `update_step_progress(..., step=0, ...)`, keeping the
  percentage in the label. When unmeasured preparation finishes, set the first
  segment complete. Remove intermediate wizard success messages that create
  additional message-bar items.
- **Depends on:** Task 1
- **Acceptance:** From-scratch schema-upgrade progress stays within the first
  third and retains percentage detail; existing-file preparation completes the
  first segment without creating another progress item.
- **Evidence:** Wizard tests verify callback mapping and the absence of the old
  standalone success notifications.

#### Task 3: Integrate upload and remote hand-off progress [P]
- **Estimate:** ~60–80 lines
- **Files:** `rana_qgis_plugin/loader.py`, relevant upload tests
- **Description:** Use the progress bar passed from the wizard. Map
  `SchematisationUploadTask.progress_changed` into the second third (step 1),
  advance to step 2 when model creation is requested, and preserve the
  Processes-panel guidance after the remote process starts. Keep existing
  failure and cancellation behavior, calling `finish_step_progress` on each
  terminal path.
- **Depends on:** Task 1
- **Parallel:** Can run with Task 2 after Task 1. Coordinate the shared
  hand-off between wizard and loader so both use the same `pb`.
- **Acceptance:** Both creation actions use the same progress item through
  upload and hand-off; the bar completes only after the remote model request
  succeeds; upload completion does not replace the hand-off guidance with a
  misleading upload-only success message.
- **Evidence:** Loader/upload tests verify signal-to-progress mapping and final
  notification behavior.

### Integration & Polish

#### Task 4: Validate complete workflows and terminal-state cleanup
- **Estimate:** ~30–50 lines
- **Files:** Tests added in Tasks 2–3; `loader.py` only if signal ordering
  requires adjustment
- **Description:** Validate both creation paths, success/failure/cancellation
  cleanup, and non-regression for unrelated progress callers such as save
  revision and downloads.
- **Depends on:** Tasks 2 and 3
- **Acceptance:** No stale progress item remains after cancellation or failure;
  both creation paths preserve the remote-process guidance; unrelated callers
  retain their current behavior.
- **Evidence:** Focused unit test suite passes and manual testing confirms both
  creation paths and the Processes-panel hand-off.

## Notes

- The three stages are equally weighted, regardless of their actual duration.
- Existing user-facing step/detail text should be retained where practical;
  no new workflow terminology is required.
- The remote model process is asynchronous and is considered complete locally
  when its start request succeeds.
- Do not modify the general `clear_msg_bar=False` behavior in this feature.
- Stateful progress reporter: deferred. A class that owns the item and step
  state is a possible future refactor of `UICommunication`, not part of this
  feature.

## Dependencies & Execution Order

- Task 1 is the foundation and blocks Tasks 2 and 3.
- Tasks 2 and 3 can proceed in parallel after Task 1.
- Task 4 follows both integration tasks.

## Progress

- [ ] Task 1: Implement the step-progress helper functions and tests
- [ ] Task 2: Integrate local-preparation progress into both wizards
- [ ] Task 3: Integrate upload and remote hand-off progress
- [ ] Task 4: Validate complete workflows and terminal-state cleanup
