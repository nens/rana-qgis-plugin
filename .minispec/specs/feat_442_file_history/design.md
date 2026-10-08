---
feature: feat_442_file_history
status: planned
created: 2026-09-28
decisions:
  - 20260928-1609-history-dialog-structure
  - 20260928-1609-history-pagination
  - 20260928-1609-history-api-errors
  - 20260928-1752-revision-action-stubs
  - 20260928-1755-legacy-migration-boundary
  - 20260928-1804-synchronous-revision-batches
  - 20260928-1808-revision-button-enablement
  - 20260928-1812-fetch-all-generic-history
  - 20260928-1823-history-dialog-base-and-siblings
  - 20260930-1132-rana-model-history-actions
  - 20260930-async-history-fetch
---

# File History Design

## Overview

Add a history window to the existing `FileAction.VERSION_HISTORY` context-menu
action. Generic files, folders, and the `Files` root item show read-only Rana
file history. Schematisation files show 3Di revision history instead, including
the legacy revision-view action columns. The `Simulation` column remains a
placeholder; the `Rana Model` column supports model creation and deletion.

Both views are modal dialogs with a table, Refresh control, and inline error
feedback. Generic history loads an initial page of up to 100 items and fetches
later pages when the user reaches the table's scrollbar bottom. It has no
manual "Load more" control. Schematisation history fetches all revisions so
its model-limit button state is complete before rendering.
The design follows the existing `FileInfoDialog` pattern. Generic history
remains informational; schematisation revision rows include `Simulation` and
`Rana Model` action columns whose enabled state follows the legacy rules. The
`Simulation` action remains a placeholder for a later feature. The `Rana
Model` action is wired to the native model creation and deletion flows.

## User Stories

### View generic Rana history (P1)

As a Rana user, I want to open the history of a file, folder, or the `Files`
root item so that I can see when it changed, who made the change, and what
happened.

**Independent test:** Open the context menu for each item type, choose
`Version history`, and verify a table containing timestamp, user, and message
is shown.

**Acceptance scenarios:**

1. Given a non-schematisation file, when `Version history` is selected, then
   the generic Rana history dialog opens for that file path.
2. Given a folder, when `Version history` is selected, then the dialog opens
   with that folder path as the history filter.
3. Given the `Files` root item, when `Version history` is selected, then the
   dialog requests project-level history without a path filter.

### View schematisation revisions (P1)

As a Rana user, I want to inspect the revision history of a schematisation so
that I can see revision number, timestamp, submitting user, commit message,
and model availability.

**Independent test:** Open a schematisation's context menu, choose `Version
history`, and verify the revision table is shown rather than generic file
history.

**Acceptance scenarios:**

1. Given a schematisation with 3Di authentication configured, when
   `Version history` is selected, then committed revisions are displayed with
   the revision-specific columns, including `Simulation` and `Rana Model`
   action columns.
2. Given 3Di authentication is unavailable, when the dialog opens, then the
   user sees an explanatory inline error instead of an unhandled exception.
3. Given a revision row is displayed, then its `Simulation` and `Rana Model`
   cells contain buttons with the legacy enabled/disabled rules. The
   `Simulation` button remains a placeholder. The `Rana Model` button starts a
   model creation request or deletes the revision's model according to its
   label and state.
4. Given a revision has no model and model creation is allowed, when the user
   selects `Create`, then the model-tracker process is started, the row's
   Create button is disabled until the next manual Refresh, and a popup offers
   a link to the online process page for that request.
5. Given a revision has a model, when the user selects `Delete` and confirms,
   then the model is deleted synchronously and the complete revision list is
   fetched again so all model-limit button states are recalculated.
6. Given a revision row is displayed, when the user opens its context menu,
   then the menu contains `Open` and `Open in web viewer` actions for that
   selected revision.
7. Given `Open` is selected for a revision, then the existing native
   schematisation-open flow downloads and opens that selected revision rather
   than implicitly opening the latest revision.
8. Given `Open in web viewer` is selected for a revision, then the existing
   Rana schematisation link is opened with the selected revision ID, matching
   the legacy URL-substitution behavior.

### Load generic history on demand (P2)

As a Rana user, I want the first history entries to appear quickly and older
entries to load as I scroll, so that opening a large history does not require
fetching the entire history first.

**Independent test:** Open the history dialog for an item with more than one
API page, verify the first page appears, then scroll to the bottom and verify
the next page is appended without a manual "Load more" interaction.

**Acceptance scenarios:**

1. Given a generic history response with a `next` cursor, when the first page
   is displayed and the user reaches the scrollbar bottom, then the dialog
   requests and appends the next cursor page.
2. Given a generic history response without a `next` cursor, then reaching the
   scrollbar bottom does not make another request.

## Components

### `HistoryDialog` (base class)

New module: `rana_qgis_plugin/widgets/version_history_dialog.py`.

`HistoryDialog` is an abstract base `QDialog` that owns everything the two
history views share: a `QTableView` backed by a `QStandardItemModel`, a
Refresh control, an inline error label, and an empty-state label. It defines
the fetch/refresh lifecycle (fetch on open, fetch again on Refresh, disable
Refresh while a request is running, route `NetworkUnavailableError` and
`RanaFetchError` to `error_signals`) as a template that calls into subclass
hooks for:

- the window title,
- the table's column headers,
- fetching and mapping rows into the table.

`HistoryDialog` itself is never instantiated directly; it has no knowledge of
Rana project APIs or 3Di APIs.

### `RanaHistoryDialog`

`RanaHistoryDialog(HistoryDialog)` implements the generic Rana history view
for files, folders, and the `Files` root. On fetch, it consumes
`get_tenant_project_file_history_page(project_id, params)` with `path` set to
the file or folder path (omitted for project-wide/root history). The dialog
requests the first page with a limit of 100 and requests later cursor pages
when the user reaches the table's scrollbar bottom. Each page is mapped to
`Timestamp | User | Message` rows and appended as it arrives.

### `SchematisationRevisionHistoryDialog`

`SchematisationRevisionHistoryDialog(HistoryDialog)` implements the
schematisation revision view. It resolves the schematisation through the
existing Rana descriptor endpoint, then uses
`ThreediCalls.fetch_schematisation_revisions()` to retrieve all revisions
synchronously.

Fetching all revisions is intentional because the legacy button enablement
depends on the total number of revisions with a Rana model. The dialog must
know that complete count before rendering the `Create` model buttons.

The revision dialog preserves the legacy table shape by including `Simulation`
and `Rana Model` action columns. Buttons use the legacy enablement rules. The
`Simulation` buttons remain placeholders; the `Rana Model` buttons are wired
to the native loader as described below.

For each revision:

- `Simulation` is labelled `New` and enabled only when
  `revision.has_threedimodel` is true. Otherwise it is disabled with the
  legacy tooltip explaining that a Rana model is required.
- `Rana Model` is labelled `Delete` and enabled when the revision has a model.
- `Rana Model` is labelled `Create` when the revision has no model. It is
  enabled while the total number of revisions with models is below the
  schematisation's `threedimodel_limit`; otherwise it is disabled with the
  legacy model-limit tooltip.

The `Create` action calls the existing native
`Loader.start_model_tracker_process()` mechanism used after revision uploads.
It starts the server-side process and does not wait for the model to become
available. The clicked Create button is disabled for the current dialog
session until the user manually refreshes the history. On a successful process
request, the dialog shows a popup with a clickable project URL using the
processes tab (`tab=2`) and the returned job ID (`job=<id>`), so the user can
track the request online. The URL uses the current project slug and tenant;
the generic processes-tab URL is the fallback if the execution response does
not include a job ID.

The `Delete` action first asks for confirmation. After confirmation, the
loader resolves the 3Di model belonging to the selected schematisation
revision and deletes it synchronously through `ThreediCalls`. A successful
delete triggers the dialog's complete revision fetch, because the model limit
is calculated across every revision. Failed deletes are reported using the
native action-error presentation and do not alter the row state.

The model count is calculated across the complete fetched revision list, not
only currently visible rows. This is why this dialog intentionally fetches
all revisions rather than using the bounded-page pattern initially considered.

The `Simulation` action remains a placeholder and has no downstream side
effects in this feature.

Like generic history, the revision dialog has no `Load more` control; the
complete revision list is loaded before the action-button state is
calculated.

Each revision row also has a context menu with two actions:

- `Open` reuses the existing native schematisation-open/download flow, passing
  the selected revision instead of letting the loader choose
  `latest_revision`.
- `Open in web viewer` reuses the schematisation's existing Rana management
  link and replaces its revision ID with the selected revision's ID, as the
  legacy `RevisionsView` does.

The context menu is attached to the revision table, so the row under the
pointer supplies the revision for both actions. No separate revision picker
or submenu is introduced.

### Legacy migration boundary

The legacy `RevisionsView` is a reference for the revision table's fields,
columns, and row-action slots. It is **not** moved into the native data-item
implementation. Its class is coupled to the legacy `RanaBrowser`, legacy
`FileAction`, `UICommunication`, legacy 3Di-auth helper, and legacy loader
signals.

The native implementation reuses the underlying, current API capabilities:

- `get_threedi_schematisation()` to resolve a file descriptor to a
  schematisation;
- `get_threedi_api()` for current 3Di authentication/client construction;
- `ThreediCalls.fetch_schematisation_revisions()` for the complete revision
  list and model-count calculation;
- the existing native schematisation-open/download flow, extended to accept a
  selected revision;
- the Rana schematisation management link from the resolved file object for
  revision-specific web-viewer URLs;
- current `ApiErrorSignals` and `FileAction.VERSION_HISTORY` conventions;
- current QGIS/Qt table and dialog patterns from `FileInfoDialog`.

The following legacy UI/application pieces are deliberately reimplemented or
deferred rather than copied:

- `RevisionsView` itself and its `busy`/`ready` lifecycle signals;
- legacy browser wiring in `legacy/widgets/rana_browser.py`;
- legacy `FileAction` values and `has_3di_authcfg()` gating;
- legacy `UICommunication` error presentation;
- the legacy revision context-menu implementation itself; its `Open` and
  `Open in web viewer` behavior is reimplemented through the native action,
  loader, and file-object paths;
- the legacy `Export to gpkg` and `Open in local folder` revision actions;
- the concrete Simulation callback; its column is retained as a stub for a
  later feature.

Rana Model actions are implemented through native loader methods and current
API clients rather than through legacy signals or `RevisionsView`.

Legacy behavior is therefore used as a field/UX reference, while integration
is implemented through the current native data-item and widget architecture.

### Revision wrapper compatibility

`ThreediCalls.fetch_schematisation_revisions()` is currently used by
non-legacy simulation and upload code as well as legacy code. The history
dialog reuses its existing all-pages behavior because the complete list is
needed for exact model-limit enablement. The implementation must not change
that method's contract.

`fetch_schematisation_revisions_with_count()` remains available for future
bounded-page use, but is not required by the initial revision-history design.

### Context-menu wiring

`FileAction.VERSION_HISTORY` is added to every result of `get_file_actions`.
`RanaFileDataItem.actions` opens `RanaHistoryDialog` for every file except
`threedi_schematisation`, for which it opens
`SchematisationRevisionHistoryDialog`. `RanaFolderDataItem.actions` opens
`RanaHistoryDialog` with its `folder_path`. `RanaFilesDataItem` inherits this
behavior with an empty path, representing project-level history.

## Data Model

### Generic Rana history

The project endpoint returns cursor pages with `items` and optional `next`.
Each item contains:

- `created_at`: ISO timestamp
- `message`: change description
- `committed_by`: user object containing names and/or email

The table columns are `Timestamp`, `User`, and `Message`. User display uses
given and family name, then email, then `Unknown` as fallback.

### Schematisation revision history

The existing 3Di client returns revision objects with at least:

- `number`
- `commit_date`
- `commit_user`
- `commit_message`
- `has_threedimodel`

The table columns are `#`, `Timestamp`, `User`, `Message`, `Simulation`, and
`Rana Model`. Buttons use the legacy enabled/disabled rules. The `Simulation`
button remains a placeholder; `Rana Model` buttons invoke the model actions
described below.

The revision row context menu contains `Open` and `Open in web viewer`. The
selected revision object supplies the revision ID and number to both actions.

## API / Interface

### Rana file history

`get_tenant_project_file_history_page(project_id, params)` uses the standard
raise-on-error fetch path and returns exactly one cursor page, including its
`items` and optional `next` cursor. The native dialog owns the cursor state,
requests pages with a limit of 100, and only requests the next page when the
user reaches the scrollbar bottom.

### Schematisation revisions

The initial implementation calls
`ThreediCalls.fetch_schematisation_revisions()` and intentionally receives the
complete revision list. It counts `has_threedimodel` across that list and
compares the count with `schematisation.threedimodel_limit` before rendering
the `Rana Model` buttons. Enabled `Simulation` buttons open a minimal
placeholder dialog with no downstream API call. `Rana Model` buttons use the
concrete callbacks below.

The Create callback calls `Loader.start_model_tracker_process()` with the
current project, schematisation, and revision context. That method returns the
execution response from `start_tenant_process()` while retaining its existing
error presentation. The dialog disables the clicked Create button until a
manual Refresh and shows a popup containing a clickable process-page URL. The
URL uses the project page's `tab=2` processes view and the returned job ID when
available; otherwise it links to the generic processes tab.

The Delete callback confirms with the user, then calls a synchronous loader
method that resolves the selected revision's 3Di model and deletes it through
`ThreediCalls`. It returns a displayable error string on failure. A successful
delete runs the complete revision fetch again so the model count and every
Create button are recalculated.

The revision context-menu actions use the row's selected revision:

- `Open` passes that revision through the existing native schematisation
  downloader/open flow. The default file open behavior remains unchanged and
  continues to use the latest revision when no explicit revision is supplied.
- `Open in web viewer` starts from the resolved schematisation's existing
  management URL and substitutes the selected revision ID before calling
  `QDesktopServices.openUrl()`.

The revision action interface additionally requires the dialog to have access
to the native `Loader`, project ID, project slug, schematisation ID/name, and
selected revision ID. The loader's model-tracker start method returns the
execution response (while preserving its existing UI error handling), allowing
the dialog to construct the job-specific online process link. A small URL
helper may centralize construction of the project processes URL, following
`get_rana_file_url()`.

The loader exposes a synchronous deletion method returning `None` on success
or an error string on failure. It uses the current 3Di client and
`ThreediCalls.fetch_schematisation_revision_3di_models()` followed by
`delete_3di_model()`. 3Di `ApiException` failures are converted with the
existing `extract_error_message()` helper before being returned to the dialog.

`Export to gpkg` and `Open in local folder` are not ported in this feature.

### Error handling

- `NetworkUnavailableError` emits `error_signals.connection_lost` and shows
  `No connection to Rana`.
- `RanaFetchError` emits `error_signals.fetch_error_occurred` and shows an
  inline history-load error.
- Missing 3Di API authentication shows an inline explanatory error.
- A failed model deletion is shown as an action error after confirmation; the
  history table is not refreshed as though the deletion succeeded.
- A successful model-creation request shows the process-link popup and leaves
  the row disabled until manual Refresh; completion of the server-side job is
  not polled by the dialog.
- An empty successful response shows `No history yet` rather than a blank
  unexplained table.

### UI lifecycle

Both generic history and schematisation revisions are fetched completely on
open, while generic history pages are appended progressively as they arrive.
Because complete fetching made the GUI noticeably slow for long histories,
network fetching and row-data preparation run in a `QgsTask`. Refresh is
disabled and a loading state is shown while a task is active.
`QStandardItem` creation and table updates happen only in GUI-thread signal
handlers. Closing the dialog cancels the active task and stale results from
an older refresh are ignored.

## Open Questions

- If complete fetching remains slow after moving it to a `QgsTask`, consider
  an aggregate model-count endpoint or a bounded/virtualized table without
  changing the API/data boundary.
- A future feature will replace the `Simulation` stub with a concrete action
  and API integration.
- A future feature may add `Export to gpkg` and `Open in local folder` actions
   for a revision; those remain intentionally outside this change.

## Manual UI Test Paths

- File context menu: vector, raster, scenario, and other file.
- Schematisation context menu with and without 3Di authentication.
- Subfolder context menu.
- `Files` root context menu.
- Large generic history sets (first page on open, later pages on scroll).
- Schematisation revision button enablement, model actions, and the remaining
  Simulation placeholder.
- Revision-row context menu: `Open` downloads/opens the selected revision, and
  `Open in web viewer` opens the selected revision URL.
- Revision-row `Rana Model` actions: Create starts a process, disables the
  clicked button, and opens the online process link; Delete confirms, removes
  the model, and refreshes all revision states.
- Verify the `Simulation` action remains a placeholder and makes no request.
- Confirm that the default schematisation `Open in QGIS` action still opens
  the latest revision when invoked outside revision history.
- Network failure and empty-history states.
