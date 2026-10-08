---
type: decision
id: 20261008-1530-schematisation-explanation-step
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/
tags: [schematisation, wizard, user-experience]
participants: [engineer, implementation-agent]
---

# Keep the from-scratch explanation step

## Context

The legacy from-scratch wizard contains an explanation page before its settings
page. The current plugin does not yet have this creation wizard, so the port
can either preserve or remove that part of the flow.

## Options Considered

### Option 1: Keep the explanation step

Retain an explanation page in the from-scratch flow before users configure
their new schematisation.

- ✅ Preserves the guided legacy flow and provides context before setup.
- ❌ Adds a wizard step that does not collect input.

### Option 2: Skip the explanation step

Go directly from schematisation details to actionable settings.

- ✅ Shortens the wizard.
- ❌ Removes the explanation currently provided to users.

## Decision

Keep the explanation step in the from-scratch flow when porting it.

## Consequences

### Positive

- ✅ Users retain the explanatory context before configuring a new schema.

### Negative

- ⚠️ The wizard has one additional non-input step.

## Code References

- Legacy page: `rana_qgis_plugin/legacy/widgets/new_wizard_pages/explain.py`

## Related Decisions

- `20260511-1413-split-schematisation-wizard`

## Notes

This does not define the exact text/layout of the page; porting should inspect
and preserve its useful explanation in the current UI conventions.
