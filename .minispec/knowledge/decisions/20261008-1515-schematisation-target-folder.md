---
type: decision
id: 20261008-1515-schematisation-target-folder
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/data_items/folder_item.py
  - rana_qgis_plugin/loader.py
tags: [schematisation, folder, user-experience]
participants: [engineer, implementation-agent]
---

# Use the invoking folder as the schematisation destination

## Context

The Add schematisation submenu is available from the Files root and folder
items. Each route needs a destination within the Rana project. Asking for a
second destination after the user invoked an action on a particular folder
would duplicate context already present in the Browser.

## Options Considered

### Option 1: Use the invoking folder

Pass the folder item's path to the selected route; the Files root represents
the project root.

- ✅ Matches the existing upload-file and create-folder context actions.
- ✅ Keeps the destination explicit and avoids another dialog.

### Option 2: Prompt for a destination

Open a destination picker after choosing a route.

- ✅ Allows changing the target folder during the flow.
- ❌ Adds a redundant step and may not match where the action was invoked.

## Decision

All three routes use the folder item where **Add schematisation** was invoked
as the target. Invoking the action on the Files root targets the project root.
No additional destination picker is shown.

## Consequences

### Positive

- ✅ All routes have the same clear destination behavior.
- ✅ Reuses the existing folder action contract that passes `folder_path`.

### Negative

- ⚠️ Users who want a different destination must invoke the action on that
  folder instead.

## Code References

- Existing folder action pattern:
  `rana_qgis_plugin/data_items/folder_item.py`

## Related Decisions

- `20261008-1510-schematisation-action-submenu`

## Notes

The HCC import route, like the upload routes, copies/creates the Rana-side
schematisation in this target folder.
