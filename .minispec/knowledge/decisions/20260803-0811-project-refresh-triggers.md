---
type: decision
id: 20260803-0811-project-refresh-triggers
date: 2026-08-03
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/rana_qgis_plugin.py
  - rana_qgis_plugin/data_items/rana_item.py
tags: [browser, projects, refresh, focus, ux]
participants: [engineer, implementation-agent]
---

# Two refresh triggers: manual and OS focus-regain

## Context

Projects can be added remotely. The list should stay reasonably fresh without
requiring the user to manually refresh every time. We also want to avoid unnecessary
fetches when focus moves between QGIS-internal dialogs.

## Options Considered

### Option A: Timer-based polling
- ✅ Predictable cadence
- ❌ Fetches even when user is not actively working
- ❌ Arbitrary interval choice

### Option B: Focus-regain only
- ✅ Refresh happens exactly when user returns to QGIS from external work
- ✅ Proven pattern from legacy plugin (commit b96a29e)
- ❌ No refresh if user never leaves QGIS

### Option C: Manual refresh only
- ✅ Simplest
- ❌ User must remember to refresh

### Option D: Manual + focus-regain (chosen)
- ✅ Covers both active and passive usage patterns
- ✅ No background polling overhead

## Decision

We chose **Option D**: manual refresh via context menu action, plus automatic refresh
on OS-level focus-regain.

Focus-regain logic uses the `externally_deactivated` guard from legacy commit b96a29e:
only trigger refresh when `QApplication.activeWindow() is None` on `WindowDeactivate`,
and only act on `WindowActivate` if that flag is set. This prevents spurious refreshes
when QGIS-internal dialogs open and close.

The focus logic lives in `RanaQgisPlugin` (not in the data item), as application-level
event concerns belong at the plugin lifecycle level. `RanaQgisPlugin` holds a reference
to the root item and calls `root_item.refresh()`.

This same mechanism will serve file listing and other future child item types without
changes to the trigger logic.

## Consequences

### Positive
- ✅ Users returning from external work get a fresh list automatically
- ✅ No unnecessary fetches from internal dialog interactions
- ✅ Trigger logic centralised and reusable for future child types

### Negative
- ⚠️ No refresh if user stays in QGIS continuously for extended periods

## Code References

- Legacy focus-regain fix: `rana_qgis_plugin/legacy/widgets/rana_browser.py` (commit b96a29e)
- `rana_qgis_plugin/rana_qgis_plugin.py` — `RanaQgisPlugin.initGui` / event filter
