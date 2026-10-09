---
type: decision
id: 20261008-1510-schematisation-action-submenu
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/data_items/file_actions.py
  - rana_qgis_plugin/data_items/folder_item.py
tags: [schematisation, context-menu, user-experience]
participants: [engineer, implementation-agent]
---

# Add schematisation submenu

## Context

The current plugin exposes upload-file and create-folder actions on the Files
root and folder items. This feature adds three schematisation routes at those
same locations: import from HCC, upload an existing schematisation, and create
one from scratch. Listing all three directly risks making each context menu
crowded.

## Options Considered

### Option 1: One action with a submenu

Show one **Add schematisation** context-menu entry with a submenu containing
the three routes.

- ✅ Keeps root and folder context menus compact.
- ✅ Makes the three related routes discoverable together.
- ❌ Adds a menu-navigation step before starting a route.

### Option 2: Three direct context-menu actions

List each route as an independent action on the Files root and every folder.

- ✅ Starts each route directly.
- ❌ Adds three entries to all applicable context menus.

## Decision

Use one **Add schematisation** action with a submenu for **Import from HCC**,
**Upload existing**, and **From scratch**.

## Consequences

### Positive

- ✅ Related routes are grouped under a single entry on the Files root and
  folder context menus.
- ✅ The menu remains less cluttered than exposing three peer actions.

### Negative

- ⚠️ Users take one additional menu-navigation step to choose a route.

## Code References

- Existing root/folder context action pattern:
  `rana_qgis_plugin/data_items/file_actions.py` and
  `rana_qgis_plugin/data_items/folder_item.py`

## Related Decisions

- `20260511-1413-split-schematisation-wizard`

## Notes

This decision covers the context-menu presentation only; the workflows behind
each submenu item are designed separately.
