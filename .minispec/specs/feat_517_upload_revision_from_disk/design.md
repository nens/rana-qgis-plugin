---
feature: feat_517_upload_revision_from_disk
status: planned
created: 2026-11-19
decisions:
  - 20261119-1224-upload-wip-action-availability
  - 20261119-1235-remove-not-loaded-in-editor-warning
  - 20261119-1250-split-commit-paths
  - 20261119-1310-hand-over-open-wip-to-opened-path
  - 20261119-1345-group-helpers-in-layer-manager
  - 20261119-1430-schematisation-upload-lock
---

# Upload Local WIP Revision from the File Context Menu

## Overview

Add a context-menu action for schematisations that uploads the local work in
progress (WIP) revision as a new revision without first opening the
schematisation. The action is always shown; prerequisites are checked on click.
After the user confirms the WIP folder, the normal commit flow runs
(`UploadWizard`, then `SchematisationUploadTask`) through shared code. Only one
revision upload per schematisation can run at a time, whichever entry point
started it.

## User Stories

- As a user, I want to upload my local WIP of a schematisation straight from the
  file browser so I don't have to open it in QGIS first.
- As a user, I want to see which local folder will be uploaded and confirm it
  before the upload starts.
- As a user, I want clear guidance when there is no local WIP.
- As a user, I want unsaved edits in an open WIP handled the same way as when I
  upload from the layer panel.
- As a user, I want to be stopped, with an explanation, when I try to upload a
  revision while one of the same schematisation is still uploading.

## User Flow

1. The user right-clicks a `threedi_schematisation` item and chooses
   "Upload local revision".
2. The loader resolves the schematisation id from the descriptor
   (`get_threedi_schematisation`, a network call).
3. Not authenticated or failed lookup: message and stop.
4. Upload of this schematisation already running: message and stop.
5. The loader looks up the local WIP (`list_local_schematisations`, disk only).
   No local WIP, no schematisation DB in the WIP, or an `OSError` during the
   lookup: dialog with one sentence explaining how to get a WIP, then stop.
6. WIP found: confirm dialog "Upload local work in progress from `<folder>` as a
   new revision?" (Upload / Cancel).
7. After confirming, the loader looks for an open layer group for the WIP DB:
   - Found: `commit_opened_revision(group, parent)` (unsaved-edits prompt: Save
     changes / Discard changes / Cancel; the group's revision number is updated
     after a successful upload).
   - Not found: `save_revision` directly.
8. `save_revision` runs the existing flow: `UploadWizard` (start page, model
   check, file selection, commit message), then `SchematisationUploadTask`, and
   holds the upload lock until the task ends.

## Components

### File action

`FileAction.UPLOAD_LOCAL_REVISION` ("Upload local revision", `icons.upload_icon`),
included only for `threedi_schematisation` items in `get_file_actions`. Its
callback in `RanaFileDataItem.actions` delegates to the loader. No API calls or
disk scans while the menu is built. No tooltip.

### Upload lock (on `Loader`)

In-memory set of schematisation ids with a running revision upload task, and
`is_revision_upload_in_progress(schematisation_id)`. `save_revision` refuses to
start when locked, adds the id when it starts the task, and removes it on
`taskCompleted` / `taskTerminated`. `save_initial_revision` does not use it.
Replaces the `rana/schematisation_uploading` group property and
`_GROUP_LOCKED_KEY`, which are removed.

### Loader methods

- `save_revision(project_id, schematisation_id, revision_number,
  schematisation_db_filepath, parent)`: shared core. Lock check, auth check,
  fetch schematisation and organisation, `LocalSchematisation(create=False,
  parent_revision_number=...)`, `UploadWizard`, task wiring and lock. Returns the
  task. No layer or editor knowledge; the "not loaded in Rana Schematisation
  Editor" warning is removed.
- `commit_opened_revision(group, parent)`: reads `rana/project_id`,
  `rana/schematisation_id`, `rana/revision_number` and
  `rana/schematisation_db_filepath` from the group; lock check; unsaved-edits
  prompt; `save_revision`; `attach_revision_number_update`. Called from
  `layer_tree_menu.py` and from `commit_stored_revision`. The prompt now precedes
  the network fetch. Saving layer changes keeps its error handling: a failed save
  or an `OSError` / `ValueError` reports via `bar_error` and starts nothing.
- `commit_stored_revision(project, file_item, descriptor_id, parent)`: steps 2-7
  above.

### Layer-group helpers (`layer_manager.py`)

- `find_schematisation_group(db_filepath)`: the layer group whose
  `rana/schematisation_db_filepath` matches the WIP DB (normalized path
  comparison), or `None`.
- `attach_revision_number_update(group, task)`: set `rana/revision_number` on
  `upload_succeeded`. Extracted from `layer_tree_menu.save_revision`.

### Layer panel

`layer_tree_menu.save_revision` becomes a call to
`loader.commit_opened_revision(group, parent)`. "Save revision" stays disabled
while an upload runs, now via `loader.is_revision_upload_in_progress(...)`.

### Cleanup

- Delete `is_loaded_in_schematisation_editor` (`utils/qgis.py`); its only caller
  was the removed warning.
- Delete `_GROUP_LOCKED_KEY` and all reads/writes of
  `rana/schematisation_uploading`.

## Data and API

No new API wrappers. Uses `get_threedi_schematisation(descriptor_id)` for
schematisation id and name, `list_local_schematisations(hcc_working_dir())` and
`LocalSchematisation.wip_revision` for the WIP, and the WIP's DB path and parent
revision number as inputs to `save_revision`. `hcc_working_dir()` always creates
the folder, so there is no "no working directory" case.

## Failure Cases

| Case | Behaviour |
|---|---|
| Not authenticated | `bar_error`, same wording as `save_revision` |
| Descriptor lookup fails | `show_warn` with extracted error message |
| Upload of this schematisation already running | Message "A revision of this schematisation is already being uploaded. Wait until it has finished."; nothing starts |
| No local WIP | Dialog with a one-sentence instruction |
| WIP present but no schematisation DB (`schematisation_db_filepath` is `None`) | Treated as no WIP |
| `OSError` during local lookup (e.g. WIP `schematisation/` folder missing, working dir unreadable) | Treated as no WIP |
| Saving unsaved layer changes fails | `bar_error` naming the layer; nothing starts |

## Scope Boundaries

Covers the action, the two commit paths around the shared core, the group
helpers and the upload lock. Does not cover:

- Uploading a stored (non-WIP) local revision.
- Hiding or disabling the file action based on local state (decision 1224,
  option B).
- Locking `save_initial_revision`.
- E2E tests (need explicit permission).
- Changes to `UploadWizard` or `SchematisationUploadTask`.

## Manual Testing

- Right-click a schematisation with a local WIP that is not open: confirm dialog
  shows the folder; Upload leads into the normal upload wizard and the revision
  is created.
- Right-click a schematisation with no local WIP: guidance dialog, nothing starts.
- Right-click while the WIP is open in QGIS with unsaved edits: confirm dialog,
  then Save / Discard / Cancel prompt; after upload the group's revision number
  is updated (then use "Save revision" from the layer panel on that group once
  more to check no stale parent number).
- Right-click while the WIP is open without edits: no prompt; upload works.
- During an upload (from either entry point): "Upload local revision" on the same
  schematisation shows the "already being uploaded" message; layer-panel "Save
  revision" for it is disabled. Both work again after the upload finishes or
  fails.
- Layer panel "Save revision": unsaved-edits prompt still appears, no "not loaded
  in editor" warning, upload works.
- Not logged in, and a deliberately deleted WIP gpkg.
- Cancel at each step (confirm dialog, prompt, wizard) starts nothing and leaves
  no lock behind.

## Open Questions

- Exact wording of the no-WIP sentence: "No local work in progress found for
  '`<name>`'. Open the schematisation first to create one." (to be confirmed
  during implementation).

## Resolved Details

- The folder shown in the confirm dialog is `wip_revision.main_dir`, i.e.
  `<working_dir>/<schematisation name>/work in progress/` (from
  `threedi-mi-utils`, `working_dir/working_dir.py`).
- The revision number passed to `save_revision` from the stored path is
  `wip_revision.number`, which is the WIP's parent revision number. When handed
  over to an open group, the group's `rana/revision_number` is used.
- Check `wip_revision is None` before using the DB path;
  `LocalSchematisation.schematisation_db_filepath` raises without a WIP.
- `wip_revision.schematisation_db_filepath` returns `None` when no schematisation
  DB (`.gpkg` or `.sqlite`) is found, and raises `FileNotFoundError` when the
  `schematisation/` subfolder is missing (`os.listdir`).
