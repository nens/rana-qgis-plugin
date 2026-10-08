---
type: decision
id: 20260928-1609-history-dialog-structure
date: 2026-09-28
status: superseded
supersedes: null
superseded_by: 20260928-1823-history-dialog-base-and-siblings
impacts:
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/data_items/file_item.py
  - rana_qgis_plugin/data_items/folder_item.py
tags: [file-history, qt, ui]
participants: [engineer, implementation-agent]
---

# Reuse a Base History Dialog for the Two History Sources

## Context

Generic Rana file history and schematisation revision history come from
different APIs and have different row fields. They nevertheless share the
same window lifecycle: open a modal window, refresh it, and inspect a table.

The legacy `RevisionsView` also contains Simulation and Rana Model action
columns. The exact action behavior is not part of this feature, but the
revision table must preserve those row-action slots as stubs.

## Options Considered

### Option 1: Base history dialog with a schematisation subclass

Share the table/window lifecycle in `HistoryDialog` and override the data
fetch, row mapping, and revision-specific action columns in
`SchematisationRevisionHistoryDialog`.

- ✅ Matches the existing `FileInfoDialog` / schematisation subclass pattern.
- ✅ Avoids duplicating error, refresh, and pagination controls.
- ✅ Keeps the two API domains explicit.
- ❌ The subclass must preserve the base dialog lifecycle.

### Option 2: Two independent dialogs

Implement all UI lifecycle code separately in two dialog classes.

- ✅ Each class can evolve independently.
- ❌ Duplicates refresh, error, and table behavior.
- ❌ Makes small UX differences likely.

### Option 3: One dialog with internal data-type branches

Use one class with conditional logic for both APIs.

- ✅ Fewest classes.
- ❌ Couples unrelated API models in one method.
- ❌ Makes the dialog harder to read and extend.

## Decision

We chose **Option 1: Base history dialog with a schematisation subclass**
because it reuses the established file-information dialog structure while
keeping generic history and revisions separate at the data boundary.

Generic history is read-only. The schematisation subclass includes the legacy
`Simulation` and `Rana Model` columns as placeholder row-action stubs. The
stubs have no concrete side effects; their action behavior is deferred.

## Consequences

### Positive

- ✅ Consistent modal behavior for all history types.
- ✅ Smaller implementation than reproducing the legacy revision view's full
  action behavior.
- ✅ Future asynchronous fetching can be added at the shared lifecycle.

### Negative

- ⚠️ The base class must support both cursor and offset pagination hooks.
- ⚠️ Revision-specific error handling and action-stub rendering remain in the
  subclass.

## Code References

- Existing dialog pattern: `rana_qgis_plugin/widgets/file_info_dialog.py:142`
- Legacy reference only: `rana_qgis_plugin/legacy/widgets/revisions_view.py:29`

## Related Decisions

- `20260810-1101-file-info-dialog-fetching`
