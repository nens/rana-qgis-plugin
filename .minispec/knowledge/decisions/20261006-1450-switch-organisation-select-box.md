---
type: decision
id: 20261006-1450-switch-organisation-select-box
date: 2026-10-06
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/rana_qgis_plugin.py
  - rana_qgis_plugin/widgets/tenant_selection_dialog.py
  - rana_qgis_plugin/widgets/ui/tenant_selection_dialog.ui
tags: [ui, organisation, tenant, qgis]
participants: [engineer, implementation-agent]
---

# Use a scrollable organisation select box

## Context

The Switch Organisation modal currently creates one radio button per available
organisation in an unbounded vertical layout. This makes the modal too long
when servicedesk employees have access to many organisations. Most users have
few organisations, so the fix should remain small and should not introduce a
search workflow for an uncommon case.

## Options Considered

### Option 1: Keep radio buttons in a scrollable list

- Keeps all organisations visible as a list
- Requires a bounded scroll-area layout
- Does not address the extra visual weight of many radio buttons

### Option 2: Use a non-editable select box

- Keeps the modal compact
- The standard Qt popup supports scrolling through long lists
- Requires no search or filtering behavior

### Option 3: Use a searchable select box

- Efficient for very large organisation lists
- Adds editable-combo behavior and filtering complexity
- Is unnecessary for the normal case and the stated servicedesk need

## Decision

We chose **Option 2: Use a non-editable select box** because scrolling is
sufficient for the relatively rare case of users with many organisations, and
it solves the modal-height problem with the smallest UI change.

The modal includes a `Choose an organisation:` label immediately above the
combo box so the purpose of the control is explicit.

The existing organisation label format and OK/Cancel interaction remain
unchanged unless a later design decision changes them.

The combo-box entries will continue to display the organisation name followed
by its tenant ID, in the form `name (id)`, so similarly named organisations
remain distinguishable.

The current organisation is selected when the modal opens. Confirming without
changing the tenant does nothing, cancelling always leaves the current tenant
unchanged, and selecting a different tenant preserves the existing tenant
switch and browser-reset behavior.

## Consequences

### Positive

- ✅ The modal remains compact regardless of the number of organisations.
- ✅ Users can scroll through all organisations in the standard dropdown.
- ✅ Existing tenant-switching and browser-reset behavior can be preserved.
- ✅ Tenant IDs remain visible for servicedesk users who need to distinguish
  similarly named organisations.
- ✅ Reopening the modal clearly reflects the active organisation.

### Negative

- ⚠️ Users with very large lists must scroll rather than search.

### Neutral

- The selected organisation continues to be represented by its tenant ID; only
  the UI control used to select it changes.
- The modal still requires at least two available tenants because the menu
  action is only added in that case.

## Code References

- Current modal population: `rana_qgis_plugin/rana_qgis_plugin.py:open_tenant_selection_dialog()`
- Current modal UI: `rana_qgis_plugin/widgets/tenant_selection_dialog.py`
- Modal layout: `rana_qgis_plugin/widgets/ui/tenant_selection_dialog.ui`

## Related Decisions

- `20260729-1538-tenant-lifecycle-and-relogin`

## Notes

Manual testing should cover the Switch Organisation menu path with both a
small organisation list and a servicedesk-sized list, including selecting the
current organisation, switching organisations, and cancelling.
