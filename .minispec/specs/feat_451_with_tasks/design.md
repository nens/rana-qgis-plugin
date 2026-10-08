---
feature: feat_451_with_tasks
status: cancelled
created: 2026-08-17
related_feature: feat_451_simple_context_menu_actions
---

# Asynchronous Browser Mutations and Actions Design

> This feature is no longer relevant. The existing synchronous browser mutation
> implementation remains the accepted direction for this project.

## Overview

Refactor network-backed Rana Browser actions so slow backend requests do not
block QGIS's UI thread. The immediate `feat_451_simple_context_menu_actions`
implementation remains synchronous and is completed separately. This feature
defines the later async refactor and replaces QGIS inline rename with an
explicit dialog-based action.

This design supersedes
[20260814-1000](../../knowledge/decisions/20260814-1000-rename-via-gui-provider.md)
(replaced by
[20260817-0903](../../knowledge/decisions/20260817-0903-rename-via-dialog-supersedes-gui-provider.md))
and amends
[20260814-1001](../../knowledge/decisions/20260814-1001-loader-mutation-methods-and-signals.md)
to move rename/delete/create-directory from synchronous to asynchronous
Loader operations.

## Goals

- Keep QGIS responsive while network-backed actions are running.
- Replace inline F2 rename with a context-menu rename dialog.
- Keep mutation ownership and result signalling in the persistent `Loader`.
- Disable all actions belonging to the affected item and its currently visible
  descendants while that item's operation is active.
- Make completion safe when QGIS recreates data items during refresh.

## Non-goals

- Do not change the legacy plugin code.
- Do not globally disable unrelated projects or Browser items.
- Do not preserve Browser expansion state as part of this refactor. The dialog
  removes the F2/Enter event problem, but normal refresh behavior remains.
- Do not introduce a generic task framework before at least two operations use
  the same lifecycle.

## Operations in scope

### Rename

Remove `RanaDataItemGuiProvider` and the `Rename` capability from files and
folders. Wire the existing Rename context-menu action to a dialog. On
confirmation, submit an asynchronous Loader operation and refresh the parent
after success.

### Delete

Keep the confirmation dialog, but make the Loader operation asynchronous. The
context-menu action returns immediately and reacts to Loader completion signals.

### Create directory

The folder context menu already exposes `CREATE_DIRECTORY`, but the action is
not wired in the current implementation. Add a folder-name dialog and submit
directory creation through the same asynchronous Loader lifecycle as delete
and rename. The operation targets the selected folder's stable project ID and
folder path, then refreshes that folder after success.

Name validation and duplicate checks should be handled by the Loader/API
boundary rather than by the context-menu item. A cancelled dialog must not
start an operation. The action belongs to the selected folder; unrelated
folders and siblings remain available.

### Open in browser

This action is local: the URL is constructed from the configured Rana base URL,
tenant ID, project slug, and file path already held by the data item. It remains
synchronous and is not part of the async refactor. Opening the system browser
itself is a short synchronous UI operation.

### Other candidates

Review future or existing context-menu actions that perform network calls,
including version-history retrieval, downloads, WMS/result preparation, and
file information retrieval. They should use the same pattern when connected,
but purely local actions do not need migration.

## Proposed lifecycle

The Loader remains the persistent owner. A request method starts background
work and returns immediately; it does not return the network result.

```text
data-item action
  -> Loader.start_<operation>(stable identifiers)
  -> mutation_started(operation_id, project_id, path)
  -> background request
  -> operation_succeeded(...) or operation_failed(...)
  -> mutation_finished(operation_id)
```

Signals are used for completion and UI coordination. They are not expected to
make synchronous code asynchronous by themselves; the network call must run
outside the UI thread, using QGIS task infrastructure or an equivalent worker.

## Stable operation identity

Operation results must not depend on the original `QgsDataItem` instance,
because `refresh()` may remove it and recreate children through
`createChildren()`. Each operation carries stable values such as:

- operation ID
- project ID
- item path and, where needed, parent path
- operation type

Loader stores active operations in a dictionary keyed by operation ID. Path
checks for descendants use indexed operation metadata rather than scanning the
Browser tree.

## Action disabling

While an operation is active, all context-menu actions for the involved item
are disabled. Descendant items are also considered affected for a folder
operation. Siblings and unrelated projects remain enabled.

New data items created during refresh query Loader's active-operation state so
they cannot re-enable actions accidentally. Completion clears the operation
state and emits a finished signal on both success and failure.

## Error and refresh behavior

- Loader emits success only after the backend operation succeeds.
- Loader emits failure with a user-facing message; no success refresh occurs.
- The current item or a stable parent reference may have disappeared by
  completion. Missing UI objects are harmless; the next Browser expansion can
  fetch current data.
- Successful rename/delete refreshes the affected parent once.

## Implementation sequence

1. Add a rename dialog and replace inline rename registration/capabilities.
2. Define Loader operation signals and an operation-state representation.
3. Move delete onto the asynchronous operation lifecycle.
4. Migrate rename onto the same lifecycle.
5. Add the create-directory dialog and migrate directory creation onto the
   same lifecycle.
6. Audit remaining network-backed context-menu actions and migrate applicable
   operations.
7. Add focused tests for operation state, success/failure signals, action
   disabling, and disappearing data items.

## Manual verification paths

- Rename a file and folder through the context menu while the Browser remains
  responsive.
- Cancel rename and verify no request occurs.
- Delete a file and verify actions disable until completion.
- Create a directory in the Files root and in a nested folder; verify the
  action is cancelled cleanly and successful creation refreshes the parent.
- Trigger a slow/failing request and verify the UI remains responsive and
  actions re-enable after failure.
- Collapse or refresh the Browser subtree during an operation and verify no
  stale-item exception occurs.
- Open a file in the browser and verify the locally constructed URL is correct.
