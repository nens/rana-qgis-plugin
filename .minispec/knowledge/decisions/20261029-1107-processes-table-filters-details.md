---
type: decision
id: 20261029-1107-processes-table-filters-details
date: 2026-10-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/processes_panel.py
  - rana_qgis_plugin/utils/api.py
tags: [processes, table-model, filters, job-logs]
participants: [engineer, assistant]
---

# Processes table and filters reuse current UI patterns

## Context

Legacy's ProcessesBrowser uses a `QStandardItemModel` and custom row-index mapping (`row_map`, reindexed by hand on every insert). The current codebase already has a `QAbstractTableModel`/`QTreeView` pattern and a reusable `FilterBar`. The user's requested details-on-selection is shown in the sibling POC as job logs; legacy has no such details panel.

Legacy also defines two small, self-contained pieces with no legacy-specific coupling: `JobData` (a dataclass depending only on `convert_to_numeric_timestamp`, which already exists in the current, non-legacy `utils/time.py`) and `ProcessProgressBar` (a 10-line subclass of `ColoredProgressBar` from `threedi_mi_utils.ui`, a package already used throughout current non-legacy code, including `communication.py`). Neither depends on the legacy `QStandardItemModel`/`row_map` bookkeeping or any other legacy-only module. An initial pass at this decision treated "the UI part" as one block to rewrite, which would have thrown these away unnecessarily.

Legacy also solves long-name wrapping in the Name column with `WordWrapDelegate` (`legacy/widgets/utils_delegates.py`), a generic `QStyledItemDelegate` with no legacy-specific coupling at all (no imports beyond Qt). Word wrapping is a requirement, not optional, so this is reused rather than deferred — but it needs one fix, not a verbatim port. `setIndexWidget()` replaces what a cell *paints*, but the view still asks the column's delegate for `sizeHint()` to compute row height (with `setUniformRowHeights(False)`, which legacy also sets) — so the delegate's `sizeHint()`, not its `paint()`, is what actually makes a row tall enough for wrapped text. In legacy's own wiring, `name_item` (the `QStandardItem` for the Name column) never gets `.setText(...)` called — only `.setData(job, Qt.ItemDataRole.UserRole)` — confirmed by grepping the whole file for `name_item.setText` (no hits). `WordWrapDelegate.sizeHint()` reads `index.data(Qt.DisplayRole)` via `initStyleOption`, which is therefore empty for this column, so its wrap-height calculation is very likely computing from an empty string rather than the actual job name — the delegate is wired with the right intent but likely does not achieve real multi-line wrapping as legacy has it. The fix is one line: also set `name_item.setText(job.name)` (display-role text purely for the delegate's `sizeHint()` to measure; the actual cell painting still comes from the `QLabel` index widget) when building each row.

## Options Considered

### Option 1: Port legacy table/model wholesale

Keep legacy's `QStandardItemModel`, `row_map`, and `setIndexWidget` row-position bookkeeping as-is.
- ✅ Maximum visual/behavioral parity.
- ❌ Carries forward the O(n) manual reindex on every insert and the row-position-coupled widget identity — a concrete, nameable fragility, not just a style mismatch.

### Option 2: Use current model/view and FilterBar patterns; reuse legacy's standalone data/widget pieces as-is

Build a `QAbstractTableModel` and `QTreeView`, configure the existing `FilterBar`, and recreate (not import) `JobData` and `ProcessProgressBar` in the new native module exactly as legacy defines them, since neither has any legacy-specific coupling.
- ✅ Consistent with current UI and reuses already-ported filtering behavior.
- ✅ `get_project_jobs` already supports `search`, `created_by`, and `status`.
- ✅ Avoids needlessly reinventing two already-correct, legacy-independent pieces.
- ❌ Requires a new row-reconciliation layer around the reused pieces.

## Decision

Use a `QAbstractTableModel`/`QTreeView` with columns Name, Process name, Who, Started, and Status/progress. Reconcile refreshed jobs by job ID to preserve selection where possible — this (not `JobData`/`ProcessProgressBar`) is the part actually being replaced, because legacy's `row_map` reindexing and row-position-coupled `setIndexWidget` calls are the concrete flaw, not the data/widget pieces themselves.

Recreate `JobData` (dataclass, in `rana_qgis_plugin/widgets/jobs_models.py` alongside the job-specific pure helpers) and `ProcessProgressBar` (QWidget, in `widgets/processes_panel.py`, importing `ColoredProgressBar` from `threedi_mi_utils.ui` directly) in current native modules — not imported from `rana_qgis_plugin.legacy`, consistent with the architecture boundary in `20260928-1755-legacy-migration-boundary`, but not redesigned otherwise, since their behavior is already suitable.

Recreate `WordWrapDelegate` as-is in `widgets/utils_delegates.py` (alongside `ContributorAvatarsDelegate`, already native), apply it to the Name column via `setItemDelegateForColumn`, keep `setUniformRowHeights(False)` on the `QTreeView`, and fix the sizeHint-input gap: set `name_item.setText(job.name)` in addition to `setData(job, UserRole)` when building each row, so the delegate's row-height calculation is driven by the real job name. Verify manually once implemented: a job with a long name should visibly wrap across multiple lines, not render a single clipped line.

Reuse `FilterBar` with name text search, dynamic contributor combo, and the nine legacy status values. Keep the name web link alongside the in-panel details view. Add `get_job_logs(job_id, params=None)` following current API helper conventions and show logs in a read-only area below the table on row selection.

Use the existing contributor avatar delegate only if the job response provides compatible user data; displaying contributor names must not depend on introducing a new avatar-fetching subsystem.

## Consequences

### Positive
- ✅ Reuses the current filter and table architecture rather than extending legacy structures.
- ✅ Reuses `JobData`, `ProcessProgressBar`, and `WordWrapDelegate` as-is instead of reinventing already-correct, legacy-independent code.
- ✅ Fixes a likely-ineffective wiring gap in legacy's own word-wrap setup rather than reproducing it unverified.
- ✅ Preserves the legacy filters and external job-link affordance.
- ✅ Logs appear in the monitor without replacing the existing web details path.

### Negative
- ⚠️ The new row-reconciliation layer (`JobsTableModel`) still needs unit coverage and manual validation.
- ⚠️ The logs endpoint helper is new and its response/error behavior must be confirmed against the current API client.
- ⚠️ The word-wrap fix is based on static analysis of Qt's row-height mechanics, not a live test against this exact legacy build; confirm the wrapping behavior (both the fix, and that it was indeed broken before) by hand once implemented.

## Code References

- `rana_qgis_plugin/widgets/filter_bar.py:FilterBar`
- `rana_qgis_plugin/widgets/projects_selection_dialog.py:ProjectsModel`
- `rana_qgis_plugin/utils/api.py:get_project_jobs`
- `rana_qgis_plugin/utils/time.py:convert_to_numeric_timestamp` (already current/non-legacy; `JobData` depends only on this)
- `rana_qgis_plugin/communication.py:6` (current, already imports `ColoredProgressBar` from `threedi_mi_utils.ui`)
- Legacy table/row-bookkeeping reference (the part being replaced): `rana_qgis_plugin/legacy/widgets/processes_browser.py:ProcessesBrowser.add_item`, `.update_state_for_job`, `.row_map`
- Legacy reusable pieces (recreated as-is in native code): `rana_qgis_plugin/legacy/widgets/processes_browser.py:JobData` (lines 53-93), `:ProcessProgressBar` (lines 22-33)
- Legacy word-wrap delegate (recreated with a one-line sizeHint-input fix): `rana_qgis_plugin/legacy/widgets/utils_delegates.py:WordWrapDelegate`; wiring gap confirmed via `grep -n "name_item\." rana_qgis_plugin/legacy/widgets/processes_browser.py` (no `.setText` call)
- POC logs panel reference: sibling `rana-plugin-poc/plugin.py:ProcessesDialog`

## Related Decisions

- `20261029-1106-processes-background-polling`

## Notes

Status-specific progress rendering and contributor data should use safe fallbacks for missing or null job fields.
