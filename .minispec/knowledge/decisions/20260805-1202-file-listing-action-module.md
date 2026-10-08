# Decision: New file_actions.py module for browser item context menus

**Date:** 2026-08-05
**Status:** Accepted

## Context

The legacy `utils_file_action.py` defines `FileAction` enum, icons, tooltips, and action-selection logic. It also imports from `legacy/auth_3di` and `FileActionSignals`, and contains logic for actions we do not need in this feature (save revision, save styling, save data, export gpkg, open in local folder).

## Decision

Create a new `data_items/file_actions.py` module. Copy the reusable parts (FileAction enum values we need, icons, tooltips) from legacy. Do not import from legacy modules.

## Reasoning

- Avoids inheriting legacy dependencies (`auth_3di`, `FileActionSignals`, live descriptor API calls at import time)
- The reduced action set is small enough that a fresh file is cleaner than filtering legacy output
- Icons and tooltips are pure data — safe to copy
- Legacy code remains untouched (per project conventions)

## Action set included

| Action | Included |
|---|---|
| OPEN_IN_QGIS | ✅ |
| OPEN_WMS | ✅ (scenario only) |
| DOWNLOAD_RESULTS | ✅ (scenario only) |
| OPEN_IN_BROWSER | ✅ |
| RENAME | ✅ |
| DELETE | ✅ |
| OPEN_IN_FILE_BROWSER | ❌ skipped |
| SAVE_REVISION | ❌ skipped |
| SAVE_STYLING | ❌ skipped |
| UPLOAD_FILE | ❌ skipped |
| EXPORT_GPKG | ❌ skipped |
| VIEW_REVISIONS | ❌ skipped |
| HISTORY | ❌ skipped |

## Consequences

- Small duplication of enum values and icon/tooltip dicts — acceptable given the size
- If legacy action set changes, this module must be updated independently
