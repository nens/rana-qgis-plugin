---
type: decision
id: 20261008-1550-hcc-import-specific-revision
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/utils/api.py
tags: [schematisation, hcc-import, revision]
participants: [engineer, implementation-agent]
---

# Import a selected HCC schematisation revision

## Context

The original legacy HCC import copied a schematisation without making the
revision explicit. Upstream changed the flow in commit
`5a603a5cce555e1ee17c132aab9edc6191053d16`, and the engineer confirmed that
this updated behavior is the one the current plugin should reproduce.

## Decision

HCC import requires the user to select both a source schematisation and one of
its revisions. The revision list is loaded for the selected schematisation,
ordered newest first, with the newest revision selected by default when one is
available. Import is enabled only after both selections are valid.

The copy request includes the source `schematisation_id`, selected
`revision_id`, and destination `path`. The destination path includes the
selected revision number using the upstream `_<#number>` suffix, in addition
to the invoking folder path. API errors are reported to the user; the import
does not auto-open the copied schematisation, and the Browser refreshes after
successful completion.

## Rationale

The source revision must be explicit and reproducible. Including its number in
the destination path distinguishes imported snapshots, and matching the
upstream behavior preserves the intended user workflow and API contract.

## Consequences

### Positive

- ✅ Users can choose and identify the exact HCC revision to import.
- ✅ Imported copies are distinguishable by revision number in their path.
- ✅ API errors are surfaced rather than treated as a successful copy.

### Negative

- ⚠️ Import requires an additional revision-list fetch and selection step.

## Code References

- Upstream behavior: commit
  `5a603a5cce555e1ee17c132aab9edc6191053d16`
- Current revision fetching: `rana_qgis_plugin/simulation/threedi_calls.py`
- Current Rana copy API wrapper: `rana_qgis_plugin/utils/api.py`

## Related Decisions

- `20261008-1510-schematisation-action-submenu`
- `20261008-1515-schematisation-target-folder`
- `20261008-1520-schematisation-success-followup`

## Notes

Reproduce the user-visible behavior and API contract, but implement the dialog,
API interaction, and refresh through current-plugin components and lifecycle
patterns rather than importing upstream/legacy widget wiring wholesale.
