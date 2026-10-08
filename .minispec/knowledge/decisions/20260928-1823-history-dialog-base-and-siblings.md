---
type: decision
id: 20260928-1823-history-dialog-base-and-siblings
date: 2026-09-28
status: accepted
supersedes: 20260928-1609-history-dialog-structure
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/data_items/file_item.py
  - rana_qgis_plugin/data_items/folder_item.py
tags: [file-history, qt, ui, class-structure]
participants: [engineer, implementation-agent]
---

# HistoryDialog as an Abstract Base with Two Sibling Subclasses

## Context

The original structure decision (`20260928-1609-history-dialog-structure`)
made `HistoryDialog` double as both "the concrete generic-history dialog" and
"the base class the schematisation dialog inherits from." That is an
asymmetric relationship: `SchematisationRevisionHistoryDialog` had to
override generic-history-specific behavior (its `project_id`/`path`
constructor args, its Rana fetch call) that it doesn't use at all.

The two dialogs actually only differ in *how the table is built*: what data
source is fetched, what the column headers are, and how a fetched item maps
to a row. Everything else — the dialog chrome, the Refresh control, the error
label, the empty-state label, and the fetch/refresh lifecycle — is identical.

## Options Considered

### Option 1: Base dialog doubles as the generic dialog (original choice)

Keep `HistoryDialog` as the concrete generic-history dialog;
`SchematisationRevisionHistoryDialog` subclasses it and overrides the parts it
needs.

- ✅ Fewer classes.
- ❌ Asymmetric: the schematisation subclass inherits generic-history
  constructor parameters and fetch logic it must discard/override.
- ❌ `HistoryDialog`'s name and interface don't clearly signal "this is also a
  reusable base class."

### Option 2: Abstract base class with two sibling subclasses

Make `HistoryDialog` a pure base class (chrome + lifecycle only, no Rana or
3Di knowledge). Add `RanaHistoryDialog(HistoryDialog)` for generic history and
keep `SchematisationRevisionHistoryDialog(HistoryDialog)` for revisions, as
two equal siblings.

- ✅ Symmetric: both subclasses only implement "how the table is built."
- ✅ `HistoryDialog` has a single, clear responsibility (shared chrome and
  lifecycle).
- ✅ Naming makes the relationship explicit: `RanaHistoryDialog` and
  `SchematisationRevisionHistoryDialog` read as clear siblings.
- ❌ One additional class compared to Option 1.

### Option 3: Two fully independent dialogs

Considered and rejected already in `20260928-1609-history-dialog-structure`
for duplicating chrome/lifecycle code; not reconsidered here.

## Decision

We chose **Option 2: Abstract base class with two sibling subclasses**.

`HistoryDialog` becomes a base class owning only the table widget, model,
Refresh control, error label, empty-state label, and the fetch/refresh
lifecycle. It exposes hooks (window title, column headers, fetch-and-map-rows)
that subclasses implement.

`RanaHistoryDialog(HistoryDialog)` and
`SchematisationRevisionHistoryDialog(HistoryDialog)` are the two concrete
subclasses. Neither inherits from the other. All prior content of
`20260928-1609-history-dialog-structure` and `20260928-1752-revision-action-stubs`
regarding read-only generic history, revision button enablement, and
placeholder click behavior still applies — this decision only changes which
class the shared behavior lives in.

## Consequences

### Positive

- ✅ Removes the asymmetric inheritance relationship.
- ✅ Each subclass only contains the code that differs.
- ✅ Naming symmetry (`RanaHistoryDialog` / `SchematisationRevisionHistoryDialog`)
  makes the two views easy to tell apart in code and context-menu wiring.

### Negative

- ⚠️ One more class than the original design.
- ⚠️ Context-menu wiring in `file_item.py`/`folder_item.py` now references
  `RanaHistoryDialog` by name instead of a single shared `HistoryDialog`.

## Code References

- Base dialog pattern precedent: `rana_qgis_plugin/widgets/file_info_dialog.py:142`
- Legacy reference only: `rana_qgis_plugin/legacy/widgets/revisions_view.py:29`

## Related Decisions

- `20260928-1609-history-dialog-structure` (superseded)
- `20260928-1752-revision-action-stubs`
- `20260928-1812-fetch-all-generic-history`
