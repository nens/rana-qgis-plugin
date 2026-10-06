# Feature Specification: Import an HCC Schematisation Revision

**Created**: 2026-09-24  
**Status**: Planned  
**Input**: User description: "The import schematisation from HCC dialog needs to be expanded with an option to choose the revision."

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.
  
  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Import a specific remote revision (Priority: P1)

As a Rana user, I want to choose a specific revision of an HCC schematisation when importing it, so that the project receives the intended version rather than an implicit latest version.

**Why this priority**: Selecting the exact source revision is the primary purpose of the feature and prevents non-reproducible imports.

**Independent Test**: Select an HCC schematisation, choose a non-latest revision, confirm the import, and verify that the Rana copy request contains that revision ID.

**Acceptance Scenarios**:

1. **Given** the HCC schematisation list is displayed, **When** the user selects a schematisation, **Then** the dialog loads its remote committed revisions.
2. **Given** revisions are available, **When** the revision table is displayed, **Then** revisions are ordered by revision number descending, the newest revision is selected, and the Ok button is enabled.
3. **Given** a revision is selected, **When** the user confirms import, **Then** the destination path is checked in the Rana project before the copy operation receives the schematisation ID, destination path, and selected revision ID.
4. **Given** the destination path already exists, **When** the overwrite choice is shown, **Then** Overwrite is selected by default and the user can cancel or choose a unique suffixed path.

---

### User Story 2 - Identify revisions from their history (Priority: P2)

As a Rana user, I want revision history details visible before importing, so that I can distinguish revisions using the same information available elsewhere in the plugin.

**Why this priority**: Revision numbers alone may not be sufficient when several revisions are available.

**Independent Test**: Open the revision selector and verify the revision number, author, date, and commit message columns are populated from HCC data, with blanks for missing optional values.

**Acceptance Scenarios**:

1. **Given** HCC returns revision metadata, **When** the table is populated, **Then** it shows Revision number, Committed by, Commit date, and Commit message.
2. **Given** optional revision metadata is missing, **When** the table is populated, **Then** the corresponding cell is blank rather than causing an error.

---

### User Story 3 - Receive clear feedback for unavailable revisions (Priority: P3)

As a Rana user, I want clear feedback when revisions cannot be loaded or copied, so that I know why the import cannot continue.

**Why this priority**: Network and API failures must not result in an ambiguous or unintended import.

**Independent Test**: Simulate revision retrieval and copy failures and verify that confirmation is disabled or the existing user-facing error mechanism reports the failure.

**Acceptance Scenarios**:

1. **Given** revisions are being retrieved, **When** the request is in progress, **Then** the revision selector and confirmation action cannot submit an incomplete selection.
2. **Given** revision retrieval fails or returns no revisions, **When** the failure is handled, **Then** the user sees an error and cannot continue with an implicit revision.
3. **Given** the Rana copy request fails, **When** the error is returned, **Then** the user-facing communication mechanism reports the import failure.

---

[Add more user stories as needed, each with an assigned priority]

### Edge Cases

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right edge cases.
-->

- The selected schematisation has no committed revisions: show an error/empty state and disable import.
- HCC returns incomplete optional metadata: display blank cells for missing author, date, or message.
- The user changes schematisation while revisions are loading: discard the stale result and only show revisions for the current selection.
- The selected revision becomes unavailable before copying: report the Rana API error; do not silently retry with the latest revision.
- The HCC revision list request fails: preserve the schematisation selection, show the error, and keep confirmation disabled.
- The user cancels the dialog: do not call the Rana copy operation.
- The destination path does not exist: copy directly without showing an overwrite choice.
- The user chooses Do not overwrite: cancel the import and show an informational message that the existing file was preserved.
- The user chooses Upload as a modified path: try `(1)`, `(2)`, and subsequent suffixes until an unused path is found.

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: The import dialog MUST allow a user to select an HCC schematisation and then retrieve its remote committed revisions.
- **FR-002**: The revision selector MUST use a table with columns Revision number, Committed by, Commit date, and Commit message, following the legacy upload wizard presentation.
- **FR-003**: The revision table MUST sort rows by revision number descending, select the first row by default, and enable the Ok button when that selection is available.
- **FR-004**: The dialog MUST retain the complete selected revision object, including its backend ID, separately from display text.
- **FR-005**: The Rana copy operation MUST receive the selected `revision_id` together with the existing schematisation ID and destination path.
- **FR-006**: The revision number MUST be used for display and ordering; the revision ID MUST be used for the Rana request.
- **FR-007**: The dialog MUST show only committed revisions retrieved from the selected remote HCC schematisation.
- **FR-008**: The confirmation action MUST remain disabled while revisions are loading, when retrieval fails, or when no revision is available; it MUST become enabled when the default latest revision is selected.
- **FR-009**: Revision retrieval and copy failures MUST be presented through the existing user-facing error communication mechanism.
- **FR-010**: Existing callers of the copy operation MUST remain compatible unless the Rana API contract requires the revision ID.
- **FR-011**: Before copying, the import flow MUST check whether the destination path already exists in the target Rana project.
- **FR-012**: If the destination path exists, the flow MUST offer Do not overwrite, Upload as a modified path, and Overwrite actions, with Overwrite selected by default.
- **FR-013**: Do not overwrite MUST cancel the import and show an informational message that the existing path was preserved.
- **FR-014**: Upload as a modified path MUST append an incrementing suffix in the form `(1)`, `(2)`, and so on until an unused path is found.

*Example of marking unclear requirements:*

- **FR-006**: System MUST authenticate users via [NEEDS CLARIFICATION: auth method not specified - email/password, SSO, OAuth?]
- **FR-007**: System MUST retain user data for [NEEDS CLARIFICATION: retention period not specified]

### Key Entities *(include if feature involves data)*

- **HCC schematisation**: The remote source selected by the user, identified by its schematisation ID and displayed name.
- **HCC revision**: A committed version returned by HCC for a schematisation, including revision ID, revision number, commit author, commit date, and commit message.
- **Rana model schematisation copy request**: The server-side operation containing project ID, source schematisation ID, destination path, and selected revision ID.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: Users can select a specific remote revision and complete an import without manually entering an ID.
- **SC-002**: The default selection is the highest-numbered committed revision for the selected schematisation.
- **SC-003**: An import request contains the revision ID corresponding to the row selected by the user.
- **SC-004**: No import is submitted when revision retrieval fails or returns no selectable revision.

## Implementation Notes

- Extend the existing `copy_threedi_schematisation` Rana API wrapper and its loader call chain to carry `revision_id`.
- Use the Rana project-file listing API for the pre-copy path check; do not use local filesystem state.
- Confirm the exact request field name and wire format against the Rana backend contract during implementation. The Rana model-schematisation representation already contains both `schematisation_id` and `revision_id`.
- Use the established HCC revision-history table presentation as the reference, including date formatting and blank fallbacks.
- Keep the schematisation table visible while showing the revision table below it; automatically select the latest revision so the existing Ok button is enabled after a valid schematisation selection.
- Build the original destination path without a revision suffix. Resolve collisions immediately before copying, with Overwrite as the default action.
- The UI path requiring manual testing is: Import schematisation from HCC → select schematisation → select a non-latest revision → import; also test no revisions, retrieval failure, cancellation, and copy failure.

## Decisions

- `20260924-1131-import-hcc-revision-selection`: Use the established revision-history table presentation and pass the selected HCC revision ID to the Rana copy operation.
