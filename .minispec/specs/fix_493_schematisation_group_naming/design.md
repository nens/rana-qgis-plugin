---
feature: fix_493_schematisation_group_naming
status: draft
created: 2026-10-13
decisions:
  - 20261013-1800-schematisation-group-naming-source
---

# Consistent Schematisation Group Naming

## Overview

When a schematisation is opened through Rana, the schematisation editor
currently chooses its own group name by guessing from the GeoPackage path.
This differs from other Rana resources, whose group or layer name is the plain
item name shown in Rana's file tree. Pass that canonical name into the editor
at load time. The editor-side API and reload/context handling are specified in
the `feat_452_schematisation_group_naming` spec in the editor repository.

## User Stories

- As a QGIS user opening a schematisation from Rana, I want its layer group
  and the editor's active-schematisation dropdown to use the plain Rana item
  name, consistent with vectors, rasters, and scenarios.
- As a user with an older editor version, I want schematisation loading to
  continue working with the existing editor-generated name.

## Components

### `Loader` (`rana_qgis_plugin/loader.py`)

The schematisation file item's full ID is already used to build `parents`.
Pass its final path component (`PurePosixPath(file_item["id"]).name`) through
to `open_rana_schematisation()` as the group name.

### `open_rana_schematisation()` (`layer_management/layer_manager.py`)

Accept the plain item name and pass it to `load_local_schematisation()` as
`group_name`. Continue adopting/tagging the group returned by the editor using
the existing Rana group-management functions.

### `load_local_schematisation()` (`simulation/utils.py`)

Add optional `group_name=None` and pass it to the editor's
`load_schematisation()` call. If an older editor raises `TypeError` because
it does not accept `group_name`, retry without that argument while retaining
`parents`. If that retry indicates that `parents` is also unsupported, use the
existing final fallback and call with only the GeoPackage path.

## Data Model

No new Rana metadata is introduced. The display name is derived from the
already available file item ID. Existing schematisation ID, revision number,

## API/Interface

- `load_local_schematisation(..., parents=None, group_name=None)` forwards
  the optional name to the editor.
- `open_rana_schematisation(..., group_name=...)` receives the final item
  name from its loader call site.
- The editor entry point becomes
  `load_schematisation(model_gpkg, parents=None, group_name=None)` in the
  companion editor-side change.

## Error Handling

Use signature-related `TypeError` detection as in the existing `parents`
fallback. Try the newest signature first, then without `group_name` while
keeping `parents`, then the legacy path-only call if `parents` is unsupported.
Re-raise unrelated `TypeError`s so real errors are not hidden.

## Scope Boundaries

- The leaf name is exactly the plain final file-item path component, with no
  WIP/revision suffix and no `Rana schematisation:` prefix.
- Does not change Rana's parent path construction or group metadata.
- Does not post-rename the editor-created group.
- Depends on the editor-side `feat_452_schematisation_group_naming` change
  for the name to appear consistently in the panel, dropdown, and loaded
  message; the fallback supports older versions during rollout.

## Manual Testing Paths

- Open a schematisation from Rana; confirm the layer group name is the plain
  item name, without a `Rana schematisation:` prefix or revision suffix.
- Confirm the editor's active-schematisation dropdown shows the same name.
- Open the same resource with an older editor version that does not accept
  `group_name`; confirm loading succeeds with the editor's previous naming.
- Confirm the existing parent hierarchy and Rana custom properties remain
  correct after opening.

## Open Questions

- None outstanding. The selected name format is the plain item name.
