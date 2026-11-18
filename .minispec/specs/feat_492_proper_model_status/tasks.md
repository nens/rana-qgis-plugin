---
feature: feat_492_proper_model_status
status: planned
created: 2026-11-17
chunk_size: adaptive
total_tasks: 4
estimated_lines: 200
---

# Proper model status (is_generating) Tasks

## Overview
Block Create/Delete of a Rana model per revision while it is generating, using the
`is_generating` filter on `GET /v3/threedimodels/`. See `design.md`.

## Task List

### Foundation

#### Task 1: Pure model-state logic + API call
- **Estimate:** ~70 lines (incl. tests)
- **Files:** `rana_qgis_plugin/simulation/threedi_calls.py`, `rana_qgis_plugin/widgets/version_history_dialog.py`, `tests/widgets/test_version_history_dialog.py`
- **Description:** Add `ThreediCalls.fetch_generating_models(schematisation_id)` (paginated, `is_generating=True`, `revision__schematisation__id`). Add a small function in the dialog module computing per-revision state (`has_model`, `is_generating`, `model_enabled`, `model_tooltip`) from revision/model/generating id sets and `model_limit`, with the union-based limit count. Inlined in the dialog module, no new file.
- **Depends on:** None
- **Acceptance:** Generating revision -> disabled + generating tooltip; generating models count toward the limit once (no double counting); limit tooltip unchanged otherwise.
- **Evidence:** New unit tests on the state function pass (parametrized).

### Core Implementation

#### Task 2: Wire into fetch_page
- **Estimate:** ~50 lines
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py`
- **Description:** `fetch_page` calls `fetch_generating_models`, uses the Task 1 function to fill row metadata (`is_generating`, `model_enabled`, `model_tooltip`); label stays Create/Delete. If `fetch_generating_models` raises, let the error propagate to the existing fetch error path (`show_fetch_error`) so no possibly wrong enabled buttons are shown.
- **Depends on:** Task 1
- **Acceptance:** Opening/Refreshing the dialog shows a disabled Rana Model button with tooltip for a generating revision.
- **Evidence:** Unit tests pass; manual check per design.

#### Task 3: Keep post-action updates consistent
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/widgets/version_history_dialog.py`, tests
- **Description:** `create_model` sets `is_generating` metadata and the generating tooltip on success. `update_action_columns_after_delete_success` must not re-enable rows with `is_generating` and counts them toward the limit.
- **Depends on:** Task 2
- **Acceptance:** After create, the row stays blocked until Refresh reports otherwise; after delete, generating rows remain disabled.
- **Evidence:** Unit test for the delete-update path passes; pre-commit hooks pass.

#### Task 4: Click-time guard on Create/Delete
- **Estimate:** ~40 lines (incl. tests)
- **Files:** `rana_qgis_plugin/simulation/threedi_calls.py`, `rana_qgis_plugin/widgets/version_history_dialog.py`, tests
- **Description:** Add `ThreediCalls.is_revision_generating(revision_id)` using `threedimodels_list(revision__id=..., is_generating=True, limit=1)` (`count > 0`). Call it at the start of `create_model` and `delete_model` (before the delete confirmation). If generating: show a message ("being generated, click Refresh"), mark the row generating (disabled + tooltip) and abort. Do not assume at most one generating model per revision. Fail closed: if the check raises, show the error and abort (no create/delete).
- **Depends on:** Task 3
- **Acceptance:** Stale enabled button clicked while the model is generating -> message shown, no create/delete call made.
- **Evidence:** Unit tests with a fake loader/calls verify no create/delete call when generating; hooks pass.

## Notes
- No parallel tasks; all edit the same dialog.
- No E2E tests proposed (needs explicit permission).
- Polling, simulation button and other dialogs deferred.

## Progress
- [x] Task 1: Pure model-state logic + API call
- [x] Task 2: Wire into fetch_page
- [x] Task 3: Keep post-action updates consistent
- [ ] Task 4: Click-time guard on Create/Delete
