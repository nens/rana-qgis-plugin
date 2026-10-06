---
feature: 20261006-144324-ticket-5047-list
ticket: 5047
status: planned
created: 2026-10-06
decisions:
  - 20261006-1450-switch-organisation-select-box
---

# Switch Organisation Select Modal Design

## Overview

The current Switch Organisation modal creates one radio button per available
tenant in an unbounded vertical layout. For servicedesk employees with many
organisations, the resulting modal is too long. Replace the radio-button list
with a compact, non-editable `QComboBox` below a `Choose an organisation:`
prompt. The combo box's standard popup provides scrolling.

The change is limited to the existing Switch Organisation menu flow. It does
not alter tenant retrieval, authentication, persistence, or organisation
selectors used by other workflows.

## User Stories

### Select an organisation from a long list (P1)

As a servicedesk employee, I want to choose an organisation from a compact
select box so that the Switch Organisation modal remains usable when many
organisations are available.

**Independent test:** Open the Switch Organisation action with a large tenant
list, open the select box, scroll through the entries, choose a different
organisation, and confirm that the tenant changes and the Rana browser resets.

**Acceptance scenarios:**

1. **Given** the user has multiple available organisations, **when** the Switch
   Organisation modal opens, **then** a select box displays the available
   organisations and the current organisation is selected.
2. **Given** the select box contains more organisations than fit in its popup,
   **when** the user opens it, **then** the user can scroll through all entries
   without the modal growing to the height of the complete list.
3. **Given** the user selects a different organisation and confirms, **when**
   the modal closes, **then** the selected tenant ID is persisted, a status
   message is shown, and the Rana browser is reset.

### Preserve the current organisation safely (P1)

As a logged-in user, I want cancelling or confirming the current selection to
leave my active organisation unchanged.

**Independent test:** Open the modal, cancel it, and then reopen it and confirm
the preselected current organisation; verify that neither action changes the
tenant or resets the browser.

**Acceptance scenarios:**

1. **Given** the current organisation is selected, **when** the user clicks
   Cancel, **then** the modal closes without changing the tenant.
2. **Given** the current organisation is selected, **when** the user clicks OK,
   **then** no tenant update, status message, or browser reset is performed.

## Components

### `TenantSelectionDialog`

Continue using the existing dialog class as the modal container. Its UI should
expose a `Choose an organisation:` label and a `QComboBox` for the organisation
selection, while retaining the existing OK/Cancel button box.

### `tenant_selection_dialog.ui`

Replace the dynamic organisation-list container used for radio buttons with a
compact layout containing the select box. The dialog should have a sensible
fixed or bounded size so its dimensions do not depend on the number of
organisations.

### `RanaQgisPlugin.open_tenant_selection_dialog()`

Populate the combo box from `self.tenants`. Each item displays the existing
format `organisation name (tenant id)` and stores the tenant ID as its user
data. Select the item matching `get_tenant_id()` before showing the modal.

After acceptance, compare the selected tenant ID with the current tenant ID.
Only a changed ID triggers `set_tenant_id()`, the existing status-bar message,
and `self.rana_browser.reset()`.

## Data Model

No data-model changes are required. The existing tenant records remain the
source of the list:

- Display label: tenant name followed by tenant ID, `name (id)`.
- Selection value: tenant ID stored as combo-box item data.
- Current value: tenant ID returned by `get_tenant_id()`.

## API/Interface

No API or external interface changes are required.

The existing menu action remains available only when more than one tenant is
available. The modal continues to use the existing `TenantSelectionDialog`
and `QDialog` accept/reject semantics.

## Edge Cases

- A tenant name containing `&` must remain displayed correctly. The current
  radio-button implementation escapes ampersands for Qt text rendering; the
  combo-box implementation must preserve equivalent visible text.
- If the current tenant ID matches an item, that item must be selected when the
  modal opens.
- Cancelling the dialog must not modify settings or reset the browser.
- Confirming the current item must be a no-op.
- The normal menu guard continues to prevent opening the selector when only
  one tenant is available.

## Scope Boundaries

This design covers only the Switch Organisation modal. It explicitly excludes:

- Organisation selectors in schematisation creation or upload workflows.
- Organisation selection in simulation-template workflows.
- Search, filtering, or editable-combo behavior.
- Changes to tenant retrieval, authentication, tenant persistence, or browser
  reset semantics.

## Manual Testing

After implementation, manually test these UI paths in QGIS:

- Open `Rana > Switch Organisation` with a normal small tenant list; verify
  labels, current selection, Cancel, and no-op OK behavior.
- Open the same modal with a servicedesk-sized tenant list; verify the dialog
  stays compact and the combo-box popup scrolls through every organisation.
- Select a different organisation; verify the tenant changes, the status
  message appears, and the Rana browser resets.
- Verify organisation selectors in schematisation and simulation workflows are
  unchanged.

## Open Questions

None. The design is intentionally limited to replacing the existing radio
button list with a scrollable, non-searchable select box.
