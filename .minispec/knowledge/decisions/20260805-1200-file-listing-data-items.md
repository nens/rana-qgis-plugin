# Decision: Use native QgsDataItem subclasses for file listing

**Date:** 2026-08-05
**Status:** Accepted

## Context

We need to display a file tree under each Rana project in the QGIS Browser panel. Two approaches were considered:
1. Native `QgsDataItem` subclasses — the same mechanism used by `RanaRootDataItem` and `RanaProjectDataItem`
2. Embed a custom widget (port of `legacy/widgets/files_browser.py`) inside the browser panel

## Decision

Use native `QgsDataItem` subclasses (Option 1).

## Reasoning

- Consistent with the existing `data_items/` pattern already established in this codebase
- QGIS Browser handles expand/collapse, lazy loading triggers, threading, and icon rendering natively
- Custom widget would break the native browser feel and require managing its own lifecycle
- The legacy `FilesBrowser` widget is a standalone dialog widget — its tree model and view are not designed for embedding as a browser sub-panel

## Consequences

- Five new `QgsDataItem` subclasses required
- Logic from legacy (icon mapping, action enum, tooltips) is ported selectively, not the widget itself
- Future browser items (e.g. Simulations) can follow the same pattern
