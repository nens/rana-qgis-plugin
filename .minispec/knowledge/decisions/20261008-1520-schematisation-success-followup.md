---
type: decision
id: 20261008-1520-schematisation-success-followup
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/data_items/folder_item.py
tags: [schematisation, browser-refresh, user-experience]
participants: [engineer, implementation-agent]
---

# Refresh the Browser without auto-opening after schematisation creation

## Context

The legacy upload-existing and from-scratch flows refresh the Browser and then
load the new local schematisation into the Schematisation Editor. The legacy
HCC import refreshes the Browser but does not automatically load the imported
schematisation. The current plugin's desired behavior should avoid surprising
side effects after an operation completes.

## Options Considered

### Option 1: Preserve the route-specific legacy behavior

Auto-open locally uploaded/created schematisations, but not HCC imports.

- ✅ Preserves legacy behavior for the two upload routes.
- ❌ Produces different post-success behavior between routes.
- ❌ Automatically opens a potentially large model as a side effect.

### Option 2: Auto-open after all routes

Refresh and open the resulting schematisation after any route.

- ✅ Consistent behavior.
- ❌ Adds an implicit action after a context-menu operation.

### Option 3: Refresh only

Refresh the Browser after successful import or upload/create, without opening
the schematisation.

- ✅ Keeps the result visible without taking an additional action on the
  user's behalf.
- ✅ Applies consistently to all three routes.
- ❌ Users who want to open it must use the separate open action.

## Decision

Use **Option 3: Refresh only**. After a route succeeds, refresh the Browser so
the new schematisation is visible, but do not automatically load/open it in the
Schematisation Editor. The user can open it through the existing open action.
Automatic chaining may be considered as a later enhancement.

## Consequences

### Positive

- ✅ All three routes have consistent, non-surprising success behavior.
- ✅ Keeps creation/import separate from opening.

### Negative

- ⚠️ Adds an explicit user action for users who want to open the new
  schematisation immediately.

## Code References

- Legacy follow-up behavior: `rana_qgis_plugin/legacy/loader.py`
- Current schematisation open action: `rana_qgis_plugin/data_items/file_item.py`

## Related Decisions

- `20261008-1510-schematisation-action-submenu`
- `20261008-1515-schematisation-target-folder`

## Notes

Browser refresh is required after success for all three routes. This decision
does not specify a process-link popup or auto-selection behavior.
