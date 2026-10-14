---
feature: 20261006-144324-ticket-5047-list
ticket: 5047
status: planned
created: 2026-10-06
chunk_size: medium
total_tasks: 3
estimated_lines: 130
---

# Switch Organisation Select Modal Tasks

## Overview

Replace the unbounded radio-button list in the existing Switch Organisation
modal with a compact, non-editable `QComboBox` below a `Choose an
organisation:` prompt. The combo box will use the standard scrollable popup,
retain the `name (id)` labels, preselect the active tenant, and preserve
existing switch, cancel, and no-op behavior.

The implementation changes only the existing modal UI, its population and
selection handler, and focused automated coverage. No new production
abstraction, API change, search behavior, or changes to other organisation
selectors are required.

## Task List

### Foundation

#### Task 1: Replace the radio-button container with a combo box

- **Estimate:** ~35 lines
- **Files:** `rana_qgis_plugin/widgets/ui/tenant_selection_dialog.ui`
- **Description:** Replace the dynamic `tenants_widget` radio-button container
  with a `Choose an organisation:` label and a named `QComboBox` for
  organisation selection. Keep the existing `Select Organisation` title and
  OK/Cancel button box, and give the dialog a compact, bounded layout whose
  size does not grow with the number of tenants.
- **Depends on:** None
- **Acceptance:** `TenantSelectionDialog` loads the updated UI and exposes the
  prompt label, combo box, and existing button box; the dialog dimensions
  remain independent of the tenant count; the radio-button container is no
  longer required.
- **Evidence:** The UI loads successfully through `loadUi`, and a focused
  Qt/QGIS test can find the named combo box.

### Core Implementation

#### Task 2: Populate and process the organisation combo box

- **Estimate:** ~45 lines
- **Files:** `rana_qgis_plugin/rana_qgis_plugin.py`
- **Description:** Update `open_tenant_selection_dialog()` to remove the
  `QButtonGroup`/`QRadioButton` flow and populate the combo box with one item
  per tenant. Display each item as `organisation name (tenant id)`, store the
  tenant ID as item data, and preselect the item matching `get_tenant_id()`.
  After acceptance, compare the selected item data with the current tenant ID.
  Preserve the existing tenant persistence, status message, and browser reset
  only when the selected tenant differs; cancellation and confirming the
  current tenant must have no side effects. Ensure organisation names
  containing `&` remain visibly correct.
- **Depends on:** Task 1
- **Acceptance:** The modal lists every tenant in a scrollable standard combo
  popup, selects the active tenant on opening, switches only to a changed
  tenant, and leaves settings, messages, and browser state untouched for
  Cancel or unchanged OK.
- **Evidence:** `py_compile`, `git diff --check`, and the existing QGIS plugin
  test pass. Focused behavior coverage for population, labels and item data,
  current-tenant preselection, changed-tenant switching, unchanged OK, Cancel,
  and an organisation name containing `&` is assigned to Task 3.

### Verification

#### Task 3: Add focused coverage and complete UI verification

- **Estimate:** ~50 lines
- **Files:** `tests/test_plugin.py`
- **Description:** Add focused QGIS/Qt coverage for the updated dialog and
  switch flow using the existing offscreen QGIS fixture and mocks/stubs where
  needed. Keep tests limited to observable behavior rather than introducing a
  new test helper or production abstraction. Run the relevant unit tests and
  pre-commit checks, then manually exercise the normal and servicedesk UI
  paths in QGIS.
- **Depends on:** Tasks 1 and 2
- **Acceptance:** Automated tests cover combo-box construction and selection
  semantics. Manual verification confirms a normal list remains usable, a
  servicedesk-sized list scrolls without an oversized modal, Cancel and
  unchanged OK are no-ops, and changing organisations shows the existing
  status message and resets the Rana browser. Other organisation selectors are
  unchanged.
- **Evidence:** Relevant `pytest` tests pass, pre-commit checks pass, and the
  manual UI paths listed in the design have been exercised.

## Dependencies & Execution Order

- Task 1 has no dependencies and establishes the UI object consumed by the
  controller.
- Task 2 depends on Task 1 because it populates and reads that combo box.
- Task 3 depends on Tasks 1 and 2 because its automated and manual checks
  verify the integrated behavior.
- There are no useful parallel implementation tasks; the controller and UI
  share the same existing modal, and the tests target their integrated result.

## Complexity Check

- Production files modified: 2 existing files.
- Test files modified: 1 existing file.
- New production files or abstractions: none.
- API, persistence schema, authentication, and unrelated organisation
  selectors: unchanged.

This is the minimal implementation that addresses the long-list problem. A
searchable combo box, reusable selector abstraction, or separate dialog model
would add complexity without solving a current requirement.

## Notes

- Use QGIS namespace imports for Qt types.
- Keep tenant IDs as the selection value even though the visible label includes
  both name and ID.
- Do not change the menu guard that exposes Switch Organisation only when more
  than one tenant is available.
- Manual UI testing is required because popup scrolling and browser reset are
  not fully represented by the existing unit-test suite.

## Progress

- [x] Task 1: Replace the radio-button container with a combo box
- [x] Task 2: Populate and process the organisation combo box
- [x] Task 3: Add focused coverage and complete UI verification
