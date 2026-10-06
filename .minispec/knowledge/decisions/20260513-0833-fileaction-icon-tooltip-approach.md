# FileAction Icon and Tooltip Approach

**Date**: 2026-05-13
**Status**: Accepted
**Context**: Adding tooltips and icons to all FileAction usages in the UI

## Decision

Add `get_tooltip(data_type)` method, `icon_path` property, and `icon` property to the `FileAction` enum using companion dictionaries (`_TOOLTIPS`, `_ICON_PATHS`). Keep `.value` as the label string (updated to new spec labels).

## Options Considered

- **A: Extend enum values to tuples** — Would break all `.value` usages, larger refactor
- **B: Companion dictionaries with properties** (chosen) — No changes to `.value` semantics, centralized on enum
- **C: Separate lookup functions** — Less discoverable, scattered

## Rationale

Option B avoids breaking the 7 existing `.value` usages while keeping icon/tooltip data co-located with the enum. The `get_tooltip()` method handles the one context-dependent case (OPEN_IN_QGIS varies by data_type) cleanly.
