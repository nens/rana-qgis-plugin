---
feature: feat_515_start_sim_from_context_menu
status: in_progress
created: 2026-11-18
chunk_size: adaptive
total_tasks: 6
estimated_lines: 250
---

# Start simulation from schematisation context menu Tasks

## Overview

Add a click-time simulation preflight to schematisation context menus. Reuse
the existing simulation wizard for valid models, guide users to Processes or
Version history for other model states, and share model creation with revision
history. See `design.md`.

## Task List

### Foundation

#### Task 1: Context-menu action wiring
- **Estimate:** ~30 lines (including tests)
- **Files:** `rana_qgis_plugin/data_items/file_actions.py`, `rana_qgis_plugin/data_items/file_item.py`, `tests/data_items/test_file_actions.py`
- **Description:** Add a Start simulation action for `threedi_schematisation` only. Wire it to the loader without performing network checks while constructing the menu.
- **Depends on:** None
- **Acceptance:** The action is present and enabled for schematisations and absent for other file types.
- **Evidence:** Focused action tests pass.

#### Task 2: Shared model-creation operation
- **Estimate:** ~45 lines (including tests)
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/widgets/version_history_dialog.py`, `tests/widgets/test_version_history_dialog.py`
- **Description:** Extract generation-state checking, tracker-process startup, job extraction and Processes navigation into a loader helper. Return an explicit outcome so revision history can update its row and button state.
- **Depends on:** None
- **Acceptance:** Both context-menu and revision-history flows use the same model-creation operation; generating revisions are not submitted again.
- **Evidence:** Unit tests cover started, generating and failed outcomes.

### Core Implementation

#### Task 3: Latest-revision simulation preflight
- **Estimate:** ~90 lines (including tests)
- **Files:** `rana_qgis_plugin/loader.py`, `tests/loader/test_loader.py`
- **Description:** Resolve schematisation metadata and the latest revision on click. Delegate valid enabled models to `start_simulation`; offer model creation when capacity allows; route generating revisions to Processes; route disabled/invalid models and exhausted capacity to Version history.
- **Depends on:** Tasks 1 and 2
- **Acceptance:** Every model/revision state follows the design flow and existing simulation setup is unchanged.
- **Evidence:** Unit tests cover valid, generating, creatable, invalid/disabled and limit-reached states.

#### Task 4: Error and boundary handling
- **Estimate:** ~35 lines (including tests)
- **Files:** `rana_qgis_plugin/loader.py`, `tests/loader/test_loader.py`
- **Description:** Verify how the API represents a missing latest revision and show the dedicated warning rather than a generic prerequisite error. Preserve existing authentication and network error handling.
- **Depends on:** Task 3
- **Acceptance:** Missing revision, missing authentication and API/network failures each produce the intended user feedback without opening a wizard.
- **Evidence:** Boundary/error tests pass.

### Validation

#### Task 5: UI and responsiveness review
- **Estimate:** ~15 lines or less
- **Files:** `rana_qgis_plugin/loader.py`, `rana_qgis_plugin/icons.py` (only if needed)
- **Description:** Review synchronous click-time API calls against the responsive-UI principle and decide whether the provisional Processing icon is acceptable. Keep the implementation synchronous unless observed latency requires a task-based change.
- **Depends on:** Task 3
- **Acceptance:** The action does not block context-menu construction; the chosen icon and click-time behavior are documented.
- **Evidence:** Manual UI check and decision recorded if behavior changes.

#### Task 6: Focused and manual validation
- **Estimate:** ~20 lines (tests only)
- **Files:** relevant test files
- **Description:** Run focused tests in the QGIS/Qt6 environment and manually exercise all paths in `design.md`. Do not add E2E tests without explicit approval.
- **Depends on:** Tasks 1–5
- **Acceptance:** Unit tests and pre-commit hooks pass; manual paths are recorded as verified.
- **Evidence:** Test output and manual verification notes.

## Notes

- No E2E tests proposed; explicit permission is required before adding them.
- No revision selector is included; the action always uses the latest revision.
- The loader receives a callback for Version history so it does not depend on the file-item dialog implementation.

## Progress

- [x] Task 1: Context-menu action wiring
- [x] Task 2: Shared model-creation operation
- [x] Task 3: Latest-revision simulation preflight
- [x] Task 4: Error and boundary handling
- [x] Task 5: UI and responsiveness review
- [x] Task 6: Focused and manual validation
