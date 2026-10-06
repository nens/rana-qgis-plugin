---
feature: feat-5035-import-with-rev
status: planned
created: 2026-09-24
chunk_size: medium
total_tasks: 5
estimated_lines: 330
---

# Import HCC Schematisation Revision Tasks

## Overview

Add remote HCC revision selection to the Import schematisation from HCC flow. The dialog will retrieve committed HCC revisions after a schematisation is selected, display the established revision-history columns, default to the newest revision, and pass the selected revision ID to the Rana copy operation. Before copying, the flow will resolve destination-path collisions in the target Rana project.

Only existing automated tests should be adapted. The changed Qt dialog flow and failure cases will be verified manually.

## Task List

### Foundation

#### Task 1: Extend the Rana copy request with a revision ID
- **Estimate:** ~55 lines
- **Files:** `rana_qgis_plugin/utils/api.py`, `rana_qgis_plugin/loader.py`
- **Description:** Extend `copy_threedi_schematisation` to accept and send the selected `revision_id` alongside the existing schematisation ID and destination path. Thread the selected revision ID through `Loader.import_schematisation_to_rana`, preserving the current destination-path behavior. Confirm the request field and error payload match the Rana API contract.
- **Depends on:** None
- **Acceptance:** A selected revision ID is included in the Rana copy request; the existing schematisation ID and path remain unchanged; failures continue through the existing Rana error mechanism.

#### Task 2: Add remote HCC revision retrieval and table population
- **Estimate:** ~70 lines
- **Files:** `rana_qgis_plugin/widgets/schematisation_browser.py`, `rana_qgis_plugin/simulation/threedi_calls.py` (or the existing HCC revision client identified during the task)
- **Description:** First identify the existing authenticated HCC/ThreeDi revision-list method, endpoint, and response fields, preferably reusing `ThreediCalls.fetch_schematisation_revisions()` if it supplies the required data. Then add the revision-selection portion of the dialog below the still-visible schematisation table. After a schematisation is selected, retrieve its committed HCC revisions and display a selectable table using the established columns: Revision number, Committed by, Commit date, and Commit message. Sort by revision number descending, select the newest row by default, retain the complete revision object on the row, render missing optional metadata as blank, and enable the existing Ok button when that default selection is available. Do not introduce any local revision data or state.
- **Depends on:** None for UI structure; use the revision identifier/data contract established by Task 1 where the data is passed onward.
- **Acceptance:** The HCC revision endpoint/client and response mapping are identified in code; selecting a schematisation loads its HCC revisions below the schematisation table; the table matches the established presentation; the newest revision is selected and enables Ok; no revision or failed retrieval leaves import unavailable.

### Core Integration

#### Task 3: Integrate selection state, loading, and import confirmation
- **Estimate:** ~75 lines
- **Files:** `rana_qgis_plugin/widgets/schematisation_browser.py`, `rana_qgis_plugin/loader.py`
- **Description:** Connect schematisation selection, revision retrieval, revision selection, and dialog acceptance into one reliable flow. Add loading/empty/error states, prevent confirmation while revisions are unavailable or loading, pass the selected revision object/ID to the loader, and ensure cancellation does not call Rana. Handle copy failures through the existing user-facing communication mechanism rather than silently falling back to another revision.
- **Depends on:** Tasks 1 and 2
- **Acceptance:** The complete flow imports the chosen revision; changing the selection uses the current schematisation’s revisions; cancellation does nothing; retrieval and copy failures are visible and do not submit an unintended import.

#### Task 4: Resolve destination path collisions
- **Estimate:** ~70 lines
- **Files:** `rana_qgis_plugin/loader.py`, relevant existing Rana project-file API helpers, `tests/` only if existing API tests apply
- **Description:** Build the destination path without a revision suffix and check the target Rana project immediately before copying. If the path exists, present the three choices Do not overwrite, Upload as a modified path, and Overwrite, with Overwrite selected by default. Cancel with an informational message for Do not overwrite. For Upload as a modified path, probe incrementing `(1)`, `(2)`, and later suffixes until an unused path is found. Use Rana project state, not local filesystem state.
- **Depends on:** Task 3
- **Acceptance:** A missing path copies directly; an existing path presents the choices; Overwrite uses the original path; Do not overwrite preserves the existing path and reports cancellation; the modified-path option selects the first unused suffix.

### Verification

#### Task 5: Adapt existing tests and perform manual UI verification
- **Estimate:** ~60 lines
- **Files:** Existing applicable test files discovered during implementation; no new Qt UI test suite
- **Description:** Update existing API/loader tests and fixtures only where current signatures, request parameters, path checks, or mocked responses change. Do not add a new automated dialog test harness. Manually verify successful latest-revision import, successful older-revision import, revision metadata display, no revisions, revision retrieval failure, copy failure, selection changes, cancellation, missing destination path, overwrite, do-not-overwrite, and unique suffix selection.
- **Depends on:** Task 4
- **Acceptance:** Existing applicable tests pass with the new `revision_id` and collision behavior, and the manual checklist covers the complete Import schematisation from HCC path and its error states.

## Notes

- The source revisions are entirely remote HCC revisions. No local revision directories, local revision models, or WIP state are part of this feature.
- Use revision number for display and ordering, but send revision ID to Rana.
- Use the established revision-history table behavior for the four metadata columns and date formatting.
- Confirm the exact Rana request wire format during implementation; the Rana response model includes both `schematisation_id` and `revision_id`.
- The constitution requires pausing after each medium-sized review chunk for approval.

## Dependencies & Parallel Opportunities

- Task 1 and Task 2 can be developed in parallel because they primarily touch different concerns, but both must agree on the selected revision object and ID contract.
- Task 3 depends on both foundation tasks.
- Task 4 depends on Task 3.
- Task 5 follows collision handling and includes the required manual verification.

## Progress

- [ ] Task 1: Extend the Rana copy request with a revision ID
- [x] Task 2: Add remote HCC revision retrieval and table population
- [x] Task 3: Integrate selection state, loading, and import confirmation
- [x] Task 4: Resolve destination path collisions
- [ ] Task 5: Adapt existing tests and perform manual UI verification
