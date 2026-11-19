---
type: decision
id: 20261119-1224-upload-wip-action-availability
date: 2026-11-19
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/data_items/file_actions.py
  - rana_qgis_plugin/data_items/file_item.py
  - rana_qgis_plugin/loader.py
tags: [context-menu, schematisation, upload, local-wip]
participants: [margriet, agent]
---

# Always show "Upload local revision" action; resolve local WIP on click

## Context

The user wants to upload a local WIP revision of a schematisation from the file
browser context menu without opening it. Ideally the action would only be shown
when a local WIP exists.

Investigation showed:

- `RanaFileDataItem` only knows `descriptor_id`, `data_type` and the file path at
  menu-build time. No schematisation id or name is present.
- The schematisation id is obtained via `get_threedi_schematisation(descriptor_id)`
  (`GET /tenants/{t}/file-descriptors/{id}/threedi-schematisation`), a network call
  that is not part of the OpenAPI spec. There is no cache of this mapping.
- `list_local_schematisations(working_dir)` reads disk only, but is keyed by
  schematisation id. Directories on disk are named by the 3Di schematisation
  name, which is not guaranteed to match the Rana file name.
- The file-listing payload documents no schematisation id for
  `threedi_schematisation` items. The deprecated, free-form `descriptor.meta`
  might contain it but this is undocumented and unverified.

## Options Considered

### Option A: Always show, resolve on click

- ✅ No network call or disk scan while the menu is built
- ✅ Consistent with `20261118-1200-context-menu-action-availability` (feat_515)
- ❌ Action is visible even when there is nothing to upload

### Option B: Show only with a local WIP, id taken from listing payload

- ✅ Matches the ideal behaviour
- ❌ Relies on an undocumented, deprecated field that may not hold the id

### Option C: Show only with a local WIP, id fetched on every menu build

- ❌ A network call on every menu open

## Decision

**Option A.** The action is always shown for `threedi_schematisation` items. On
click the loader resolves the schematisation id, looks up the local WIP and
always asks the user something:

- WIP exists: show the WIP path and ask the user to confirm before continuing.
- No WIP: show a one-sentence instruction on how to get a local WIP, and stop.

## Consequences

- No new cache or state for a convenience action.
- Option B can be added later by swapping the visibility check; the on-click
  flow stays the same.
- A click-time network request (descriptor to schematisation id) happens
  synchronously, as with "Start simulation".
