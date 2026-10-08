---
type: decision
id: 20260928-1755-legacy-migration-boundary
date: 2026-09-28
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/data_items/file_item.py
  - rana_qgis_plugin/data_items/folder_item.py
  - rana_qgis_plugin/legacy/widgets/revisions_view.py
tags: [file-history, migration, legacy, schematisation]
participants: [engineer, implementation-agent]
---

# Reimplement History UI in the Native Architecture

## Context

The legacy `RevisionsView` contains useful revision-history behavior, but it
is not an isolated component. It is wired into the legacy `RanaBrowser` and
legacy loader through signals, uses the legacy `FileAction` enum and
`UICommunication`, gates 3Di access with `has_3di_authcfg()`, and performs
synchronous work behind `busy`/`ready` signals that do not provide actual
background execution.

The new feature belongs to the native QGIS data-item architecture and must
follow current Qt/API/error-handling conventions rather than importing those
legacy lifecycle dependencies.

## Options Considered

### Option 1: Move/copy `RevisionsView` into the native feature

Reuse the legacy widget and adapt its callers.

- ✅ Preserves existing row controls and context-menu behavior.
- ❌ Carries legacy browser, loader, signal, auth, and error dependencies into
  the native code.
- ❌ Preserves synchronous lifecycle patterns known to have problems.
- ❌ Makes the native context-menu action depend on the legacy application
  shell.

### Option 2: Reimplement the native dialog using legacy behavior as reference

Reuse current API/client primitives and current dialog/data-item conventions;
selectively retain the revision fields and action-column shape from legacy.

- ✅ Keeps the native feature independent of the legacy browser.
- ✅ Preserves the useful revision table contract without copying unrelated
  actions.
- ✅ Allows current `ApiErrorSignals`, auth, pagination, and Qt patterns.
- ❌ Requires explicitly re-creating the table and row-action stubs.

### Option 3: Share a new common widget between legacy and native code

Extract the table from the legacy view and make both architectures use it.

- ✅ Could reduce visual duplication.
- ❌ Requires changing legacy code despite the feature not needing legacy fixes.
- ❌ Couples two application architectures through a new compatibility layer.
- ❌ Delays the native vertical slice for hypothetical reuse.

## Decision

We chose **Option 2: Reimplement the native dialog using legacy behavior as
reference**.

The implementation will reuse current API capabilities and native UI/error
patterns. It will not move or import `RevisionsView`, legacy browser wiring,
legacy action enums, legacy auth helpers, or legacy loader signals.

The legacy view is authoritative only for the revision data fields, button
labels/enablement, and the presence of `Simulation` and `Rana Model`
row-action columns. The `Simulation` action remains a stub. The `Rana Model`
actions are implemented through the native callbacks defined in
`20260930-1132-rana-model-history-actions`. Legacy context-menu actions for
opening, exporting, and browsing revisions are not part of this feature.

## Consequences

### Positive

- ✅ Native code remains independent of legacy lifecycle and communication
  objects.
- ✅ Known legacy threading/lifecycle issues are not reproduced.
- ✅ The feature can be tested through the current data-item action path.

### Negative

- ⚠️ Some table and row-control code is intentionally duplicated/reimplemented.
- ⚠️ Future action work must connect to the native loader/API boundaries rather
  than the legacy signal graph.

## Code References

- Legacy table and fields: `rana_qgis_plugin/legacy/widgets/revisions_view.py`
- Legacy signal wiring: `rana_qgis_plugin/legacy/widgets/rana_browser.py:367`
- Current revision API wrapper:
  `rana_qgis_plugin/simulation/threedi_calls.py:1261`
- Current schematisation resolution:
  `rana_qgis_plugin/utils/api.py:get_threedi_schematisation()`
- Current 3Di client access: `rana_qgis_plugin/utils/generic.py:get_threedi_api()`
- Current file-info dialog pattern:
  `rana_qgis_plugin/widgets/file_info_dialog.py:142`

## Related Decisions

- `20260928-1609-history-dialog-structure`
- `20260928-1752-revision-action-stubs`
- `20260930-1132-rana-model-history-actions`
