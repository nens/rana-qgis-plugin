# Decision: Import a selected HCC revision through Rana

**Date**: 2026-09-24
**Status**: Accepted
**Feature**: `feat-5035-import-with-rev`

## Context

The Import schematisation from HCC dialog currently selects a remote schematisation but does not let the user choose which committed revision is copied into the Rana project. The existing flow calls the Rana copy operation with a schematisation ID and destination path only.

The repository contains an established revision-history presentation with revision number, committed by, commit date, and commit message. The import flow should use this presentation for revisions returned by HCC.

## Decision

After a user selects an HCC schematisation, the import dialog will load and display its committed HCC revisions in a selectable table based on the established revision-history presentation. The table will show:

- Revision number
- Committed by
- Commit date
- Commit message

Rows will be sorted by revision number descending, and the newest revision will be selected by default. The full selected revision object will be retained, while the revision number is used only for display and ordering.

The schematisation table will remain visible while the revision table is shown below it. Selecting a schematisation with available revisions will automatically select the newest revision and enable the existing Ok button. The button remains disabled when revisions are loading, unavailable, or failed to load.

The import flow will extend the Rana server-side copy operation to receive the selected `revision_id` alongside the existing schematisation ID and destination path. The revision ID, rather than the revision number, is the backend identifier sent to Rana.

The destination path will not include the revision number. Immediately before copying, the flow will check the target Rana project for that path. If it exists, the user will choose between Do not overwrite, Upload as a unique suffixed path, and Overwrite, with Overwrite selected by default. Do not overwrite cancels the import and shows an informational message. The suffixed option tries `(1)`, `(2)`, and subsequent values until an unused path is found.

## Rationale

- The table matches an established legacy UI pattern and provides enough metadata to distinguish revisions.
- Selecting the newest revision by default preserves the expected common-case behavior while allowing reproducible selection of older revisions.
- Revision IDs are stable backend identifiers and are already represented in Rana model-schematisation data and other repository flows.
- Keeping the copy server-side avoids introducing a separate download/register workflow.
- Using HCC revision data keeps the import selection tied to the source version that will be copied.
- Checking the target Rana project, rather than the local filesystem, reflects the actual collision that matters for the copy operation.

## Consequences

### Positive

- Users can reproduce imports from a specific HCC revision.
- The existing import flow remains conceptually simple: select source, select revision, copy.
- The UI uses familiar revision metadata and sorting.

### Negative

- Selecting a schematisation requires an additional remote revision request.
- The Rana client wrapper, loader call chain, and likely backend request contract must be updated.
- Error and loading states need explicit handling so an unavailable revision is never silently replaced by the latest revision.
- Existing destination paths require an additional user choice and a unique-name resolution loop.

## Scope Boundaries

- Includes committed revisions returned by HCC.
- Excludes changes to unrelated revision-history views.
- Does not add metadata beyond the established four table columns.
- Does not use the revision number as part of the destination name.

## Open Implementation Detail

Confirm the exact Rana copy request wire format for `revision_id` while implementing. The supplied Rana model-schematisation example demonstrates that the backend domain model supports both `schematisation_id` and `revision_id`; the client must use the contract's exact request shape.
