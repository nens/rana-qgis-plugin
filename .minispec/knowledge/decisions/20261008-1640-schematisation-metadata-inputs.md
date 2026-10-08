---
type: decision
id: 20261008-1640-schematisation-metadata-inputs
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/
tags: [schematisation, wizard, metadata]
participants: [engineer, implementation-agent]
---

# Retain schematisation metadata inputs

## Context

The legacy Upload existing and From scratch flows collect a required name,
optional description, and owning organisation. Organisation selection is
hidden when only one organisation is available. These values are part of the
established flow and are relevant to registering/creating the schematisation.

## Options Considered

### Option 1: Retain the legacy metadata inputs

Keep name, description, and organisation/owner selection for both routes,
including hiding the selector for a single available organisation.

- ✅ Preserves the established input contract.
- ✅ Avoids forcing a redundant choice for a single organisation.

### Option 2: Collect only name and description

Remove organisation selection from these flows.

- ✅ Simpler UI.
- ❌ Could omit information needed for HCC-side schematisation setup.

## Decision

Retain the required name, optional description, and organisation/owner inputs
for both Upload existing and From scratch. Hide the organisation selector
when only one option is available.

## Consequences

### Positive

- ✅ Users retain control over schematisation ownership when choices exist.
- ✅ The UI avoids an unnecessary one-option selection.

### Negative

- ⚠️ The current UI must load available organisations and handle fetch errors.

## Code References

- Legacy metadata page:
  `rana_qgis_plugin/legacy/widgets/new_wizard_pages/name.py`
- Current HCC client: `rana_qgis_plugin/simulation/threedi_calls.py`

## Related Decisions

- `20260511-1413-split-schematisation-wizard`
- `20261008-1630-shared-schematisation-creation-flow`

## Notes

Use current authentication, API, and UI patterns to populate the selector; do
not migrate legacy communication or widget wiring.
