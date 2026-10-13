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
`group_name` argument. Do not add a WIP or revision suffix. Until the installed
editor supports the argument, use the existing TypeError feature-detection
fallback to load as before.

## Reasoning

The host already has the canonical item name. Supplying it before the editor
creates its group keeps the Layers panel, editor dropdown, and loaded message
consistent. Renaming the group after loading would only change its layer-tree
label and could break the editor's name-based group lookup on project reload.

## Consequences

Full behavior requires the editor-side `group_name` support, tracked on the
already-checked-out `feat_452` branch. Rana's fallback allows its change to
work with older editor versions without introducing a new loading failure.

## Related Decisions

- `../../specs/fix_493_schematisation_group_naming/design.md`
