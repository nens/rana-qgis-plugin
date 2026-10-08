---
type: decision
id: 20260930-1132-rana-model-history-actions
date: 2026-09-30
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/utils/generic.py
  - rana_qgis_plugin/data_items/file_item.py
tags: [file-history, schematisation, model-actions, qt, api]
participants: [engineer, implementation-agent]
---

# Wire Rana Model Actions in Revision History

## Context

The file-history design deliberately retained the legacy `Simulation` and
`Rana Model` columns as placeholders. The revision table now needs the
`Rana Model` Create and Delete actions, while the `Simulation` action remains
deferred. The legacy implementation provides the behavior to preserve, but
its browser, loader signals, and synchronous lifecycle must not be copied into
the native architecture.

The existing native loader already starts the Rana `model_tracker` process
after a revision upload. Native model deletion already calls
`ThreediCalls.delete_3di_model()` in the upload-wizard limit flow, but there is
no method that targets the model belonging to one selected revision.

## Options Considered

### Option 1: Reuse the native model-tracker process and add synchronous deletion

Use `Loader.start_model_tracker_process()` for Create, return its execution
response so the dialog can link to the online process, and add a focused
synchronous loader method for Delete.

- ✅ Reuses the already-supported server-side creation flow.
- ✅ Preserves the native loader/API boundary instead of importing legacy
  signals.
- ✅ Keeps Delete consistent with existing file deletion and model-deletion
  UI patterns.
- ❌ Create completion is not known immediately and requires manual Refresh.

### Option 2: Call the 3Di create API directly from the dialog

Call `ThreediCalls.create_schematisation_revision_3di_model()` from the row
button and manage its result in the dialog.

- ✅ Gives the dialog a direct API result.
- ❌ Bypasses the established Rana model-tracker flow used after uploads.
- ❌ Couples the widget to process/model lifecycle details and does not provide
  the online Rana process tracking link naturally.

### Option 3: Add background tasks and polling for both actions

Wrap Create and Delete in new `QgsTask` classes and poll until the model state
changes.

- ✅ Could update the row automatically when the server-side work completes.
- ❌ Adds lifecycle and cancellation complexity before observed latency
  requires it.
- ❌ Makes this history action design larger than the existing native patterns.

## Decision

We chose **Option 1: Reuse the native model-tracker process and add
synchronous deletion**.

The `Rana Model` Create button calls the existing
`Loader.start_model_tracker_process()` method. The method returns the process
execution response on success, without changing its existing error
presentation. The dialog disables the clicked Create button for the current
dialog session and shows a popup containing a clickable project URL for the
online processes tab, including the returned job ID where available. The
dialog does not poll; manual Refresh re-fetches revisions and reconciles the
temporary button state with the server.

The `Rana Model` Delete button requires confirmation. A new loader method
fetches the 3Di model for the selected schematisation revision and deletes it
synchronously through `ThreediCalls`. It returns `None` on success or a
displayable error string on failure. After success, the dialog performs its
existing complete revision fetch so the model count and every Create button
are recalculated. The `Simulation` button remains a no-side-effect
placeholder.

The process link follows the established Rana web URL shape:
`{base_url()}/{tenant}/projects/{project_slug}?tab=2&job={job_id}`. A generic
`?tab=2` project process page is used if the execution response has no job ID.

## Consequences

### Positive

- ✅ The native history dialog gains the requested model-management actions
  without importing legacy UI or lifecycle dependencies.
- ✅ Users can follow asynchronous creation in Rana's online process view.
- ✅ Delete confirmation and errors follow existing native destructive-action
  conventions.
- ✅ Full refresh after Delete preserves the global model-limit rule.

### Negative

- ⚠️ Create remains asynchronous and the dialog does not know completion until
  the user manually refreshes.
- ⚠️ The loader's process-start method must expose its execution response;
  existing callers may continue to ignore the new return value.
- ⚠️ The dialog needs project slug and loader context in addition to the
  existing schematisation and revision data.

## Code References

- Existing Create process flow: `rana_qgis_plugin/loader.py:259`
- Legacy Create entry point: `rana_qgis_plugin/legacy/loader.py:776`
- Legacy Delete flow: `rana_qgis_plugin/legacy/loader.py:895`
- Existing native model deletion: `rana_qgis_plugin/simulation/upload_wizard/model_deletion.py:172`
- 3Di model lookup/deletion wrappers: `rana_qgis_plugin/simulation/threedi_calls.py`
- Existing project/file URL construction: `rana_qgis_plugin/utils/generic.py:303`
- Existing destructive-action confirmation: `rana_qgis_plugin/data_items/file_item.py:176`

## Related Decisions

- `20260928-1752-revision-action-stubs` — remains applicable to the
  `Simulation` column; this decision implements only `Rana Model`.
- `20260928-1755-legacy-migration-boundary`
- `20260928-1808-revision-button-enablement`
- `20260928-1823-history-dialog-base-and-siblings`

## Notes

This decision intentionally does not delete or rewrite earlier decision
records. They document the design history and remain useful for understanding
why the action columns and complete revision fetch were introduced. Where this
decision narrows or changes an earlier decision, the scope is stated
explicitly above.
