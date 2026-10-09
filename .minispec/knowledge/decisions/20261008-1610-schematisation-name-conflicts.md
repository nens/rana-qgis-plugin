---
type: decision
id: 20261008-1610-schematisation-name-conflicts
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/
  - rana_qgis_plugin/loader.py
tags: [schematisation, validation, conflicts]
participants: [engineer, implementation-agent]
---

# Retain legacy schematisation name-conflict behavior

## Context

The legacy create/upload-existing flows check for an existing local
schematisation name before registering a new one. Rana rejects duplicate
remote paths during registration. These flows do not overwrite existing
schematisations.

## Options Considered

### Option 1: Retain legacy behavior

Check local name availability before creating local state, then report any
remote destination conflict returned by Rana.

- ✅ Preserves established behavior.
- ✅ Avoids destructive overwrite semantics.
- ❌ A remote duplicate is only known after the create request unless the
  current API offers a reliable preflight check.

### Option 2: Add overwrite behavior

Prompt users to replace an existing remote schematisation.

- ✅ Could support intentional replacement.
- ❌ Destructive semantics are outside the existing flow and need separate
  design.

## Decision

Retain legacy behavior: check that the schematisation name is available in the
local working directory before proceeding. Do not offer overwrite. If Rana
rejects the destination path as a conflict, report that API error to the user.

## Consequences

### Positive

- ✅ Duplicate local names are rejected early.
- ✅ Existing remote data is never overwritten by this flow.

### Negative

- ⚠️ Remote path conflicts may require a Rana create request to detect.

## Code References

- Legacy local name check and creation helper:
  `rana_qgis_plugin/legacy/widgets/schematisation_new_wizard.py`
- Current Rana create wrapper: `rana_qgis_plugin/utils/api.py`

## Related Decisions

- `20260511-1413-split-schematisation-wizard`
- `20261008-1600-existing-schematisation-file-formats`

## Notes

There is no overwrite or conflict-retry branch in this design. API errors must
be surfaced using current-plugin error communication patterns.
