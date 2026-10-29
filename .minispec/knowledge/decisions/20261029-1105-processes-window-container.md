---
type: decision
id: 20261029-1105-processes-window-container
date: 2026-10-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/data_items/project_item.py
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/widgets/processes_panel.py
tags: [processes, qgis-ui, dock-widget]
participants: [engineer, assistant]
---

# Processes window: floating per-project dock

## Context

The monitor is opened for a specific project and must remain usable while the user works in QGIS. A blocking modal dialog would prevent that. The engineer asked whether a modeless window can coexist with QGIS, whether duplicate windows should be prevented, whether docks can float, and how expensive a future container change would be.

## Options Considered

### Option 1: Blocking modal dialog

Use `QDialog.exec()`.
- ✅ Matches some current dialogs.
- ❌ Blocks QGIS interaction while monitoring, which conflicts with the feature's purpose.

### Option 2: Modeless dialog

Use a per-project `QDialog.show()`.
- ✅ Non-blocking, simple, and independently instantiated per project.
- ❌ Cannot be docked into the QGIS main window.

### Option 3: Per-project `QDockWidget`

Create one dock per project, floating by default and user-dockable.
- ✅ Non-blocking and supports both floating-window and docked use.
- ✅ Project name in the title distinguishes instances; multiple projects need no shared project switcher.
- ❌ Requires dock registration, ownership, and close/destroy cleanup.

## Decision

Use one floating-by-default `QDockWidget` per project. Keep the actual processes UI in a container-agnostic `ProcessesPanel(QWidget)` so a dialog host could replace the dock later without rewriting table, filter, or polling logic. Store open docks by project ID on `Loader`; opening an already-open project's Processes action raises/activates its existing dock. Different projects have independent docks. Since closing a `QDockWidget` normally hides it, hidden docks stop polling and can resume when raised again; remove the registry entry when the dock is destroyed.

## Consequences

### Positive
- ✅ Monitoring does not block the QGIS canvas or other UI.
- ✅ Users may dock or float the window as they prefer.
- ✅ Deduplication prevents redundant windows and polling for a project.
- ✅ A future dialog-vs-dock change is localized to the host/opening function.

### Negative
- ⚠️ More lifecycle bookkeeping than a simple modeless dialog; hidden docks remain registered until destroyed, and visibility changes must stop/resume polling correctly.
- ⚠️ Dock placement persistence is not included in this feature.

## Code References

- Project context actions: `rana_qgis_plugin/data_items/project_item.py:RanaProjectDataItem.actions`
- Loader task ownership precedent: `rana_qgis_plugin/loader.py:Loader.active_tasks`

## Related Decisions

- `20261029-1106-processes-background-polling`

## Notes

No `QDockWidget` pattern currently exists in the current plugin UI. Verify QGIS 4 / Qt 6 dock registration and teardown details during implementation.
