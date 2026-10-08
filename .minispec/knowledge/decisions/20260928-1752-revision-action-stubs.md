---
type: decision
id: 20260928-1752-revision-action-stubs
date: 2026-09-28
status: accepted
supersedes: 20260928-1609-history-dialog-structure
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/legacy/widgets/revisions_view.py
tags: [file-history, schematisation, qt, ui, stubs]
participants: [engineer, implementation-agent]
---

# Preserve Revision Action Columns with Deferred Behavior

## Context

The legacy `RevisionsView` presents schematisation revisions with separate
`Simulation` and `Rana Model` columns in addition to revision metadata. The
new file-history window should retain those columns so the revision table has
the expected shape and a place for future row actions.

At the time of this decision, the exact action behavior was not designed and
the feature therefore needed placeholders rather than concrete simulation or
model-management flows. The later model-action decision changes this for the
`Rana Model` column only; the `Simulation` column remains deferred.

## Options Considered

### Option 1: Keep both action columns with deferred behavior

Render `Simulation` and `Rana Model` columns for each revision row. Put a
button in each cell, using the legacy enabled/disabled rules, but defer the
actual downstream behavior to a later action design.

- ✅ Preserves the legacy table shape.
- ✅ Makes the future row-action extension points visible.
- ✅ Avoids prematurely choosing downstream API behavior.
- ❌ Adds UI controls that do not yet perform work.

### Option 2: Omit the action columns until behavior is ready

Show only revision metadata and add the columns in a later feature.

- ✅ Smallest immediate UI.
- ❌ Does not preserve the expected legacy revision layout.
- ❌ Requires another table-layout change when actions are added.

### Option 3: Implement the legacy actions now

Copy the simulation and Rana Model actions from `RevisionsView` into the new
dialog.

- ✅ Immediate feature parity.
- ❌ Expands this feature beyond the agreed history-window scope.
- ❌ Commits to action behavior before its separate design is complete.

## Decision

We chose **Option 1: Keep both action columns with deferred behavior** for the
initial file-history slice. The schematisation revision table contains
`Simulation` and `Rana Model` buttons, with enabled state and labels following
the legacy rules. The later `20260930-1132-rana-model-history-actions`
decision supersedes the deferred behavior for `Rana Model`: its Create and
Delete buttons now have concrete native callbacks. The `Simulation` button
remains a placeholder and must not start a simulation.

The later action design will decide the concrete callbacks, API calls, and
operation-specific error handling. Generic file, folder, and root history
remains read-only.

## Consequences

### Positive

- ✅ The revision table remains structurally compatible with the legacy view.
- ✅ Future action work can fill in established row-level extension points.
- ✅ History retrieval remains separated from action implementation.

### Negative

- ⚠️ The `Simulation` column remains an enabled-looking placeholder until its
  own action design is accepted.
- ⚠️ The placeholder dialog must clearly communicate that the operation is
  not implemented yet.

## Code References

- Legacy revision columns: `rana_qgis_plugin/legacy/widgets/revisions_view.py:242`
- New dialog planned by: `rana_qgis_plugin/widgets/version_history_dialog.py`

## Related Decisions

- `20260928-1609-history-dialog-structure` (superseded)
- `20260928-1755-legacy-migration-boundary`
- `20260930-1132-rana-model-history-actions` (supersedes the Rana Model
  portion of this decision)
