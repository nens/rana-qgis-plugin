# Decision: Rana supplies the schematisation group name explicitly

**Date:** 2026-10-13
**Status:** Accepted

## Context

When Rana opens a schematisation, the schematisation editor guesses a layer
group name from the GeoPackage path and revision-folder layout. This differs
from the naming convention for other Rana file types, whose layer or group
names use the plain file/item name displayed in Rana's file tree.

## Decision

Pass the plain leaf item name from the Rana file item's `id` to
`threedi_schematisation_editor.load_schematisation()` as the optional
`group_name` argument. Do not add a WIP or revision suffix. The editor-side
support is implemented and installed in the Docker environment used for manual
testing. Keep the TypeError feature-detection fallback for older editor
versions.

## Reasoning

The host already has the canonical item name. Supplying it before the editor
creates its group keeps the Layers panel, editor dropdown, and loaded message
consistent. Renaming the group after loading would only change its layer-tree
label and could break the editor's name-based group lookup on project reload.

## Consequences

The editor-side `group_name` support is available in the manual-test Docker
environment. Rana's fallback allows this change to work with older editor
versions without introducing a new loading failure.

## Related Decisions

- `../../specs/fix_493_schematisation_group_naming/design.md`
