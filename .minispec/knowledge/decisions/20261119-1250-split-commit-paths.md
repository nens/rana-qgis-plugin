---
type: decision
id: 20261119-1250-split-commit-paths
date: 2026-11-19
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
  - rana_qgis_plugin/data_items/file_item.py
tags: [upload, save-revision, refactor, local-wip]
participants: [margriet, agent]
---

# Split revision commit into "opened" and "stored" paths around a shared core

## Context

`Loader.save_revision` mixes two concerns: checks that only make sense for a
schematisation opened in QGIS (unsaved layer edits) and the actual
upload (API lookup, `UploadWizard`, `SchematisationUploadTask` wiring). The new
file-browser action must upload a local WIP that is not opened, reusing the same
upload code. Adding flags to skip checks would make `save_revision` harder to
reason about.

## Options Considered

### Option 1: Flags on `save_revision` to skip layer checks

- ✅ Small diff
- ❌ Boolean parameters that switch behaviour; two flows hidden in one method

### Option 2: Two entry points around a shared core

- ✅ Each entry point does only what its situation needs
- ✅ Upload logic is shared by construction, not by convention
- ❌ Touches the existing caller in `layer_tree_menu.py`

## Decision

**Option 2**, with these methods on `Loader`:

- `save_revision(project_id, schematisation_id, revision_number,
  schematisation_db_filepath, parent)`: shared core. Auth check, fetch
  schematisation and organisation, `LocalSchematisation(create=False,
  parent_revision_number=...)`, `UploadWizard`, `SchematisationUploadTask` wiring.
  Returns the task. No layer or editor knowledge.
- `commit_opened_revision(group, parent)`: reads the schematisation properties
  from the layer group, runs the unsaved-edits prompt (Save / Discard / Cancel),
  calls `save_revision` and attaches the `rana/revision_number` update to the
  task. Called from `layer_tree_menu.py` and from `commit_stored_revision`.
- `commit_stored_revision(...)`: resolves the schematisation id from the
  descriptor, finds the local WIP (`list_local_schematisations`), shows the path
  for confirmation, then calls `save_revision` with the WIP's parent revision
  number and gpkg path. If the WIP is open in QGIS it hands over to
  `commit_opened_revision`, see
  `20261119-1310-hand-over-open-wip-to-opened-path`.

In `commit_opened_revision` the unsaved-edits prompt now precedes the network
fetch (previously it followed it). Saving layer changes keeps its error handling:
a failed save or an `OSError` / `ValueError` reports via `bar_error` and stops.

Concurrent uploads are prevented by the loader, see
`20261119-1430-schematisation-upload-lock`.

## Consequences

- `test_save_revision_requires_authenticated_api` keeps working unchanged, as
  `save_revision` retains its signature.
