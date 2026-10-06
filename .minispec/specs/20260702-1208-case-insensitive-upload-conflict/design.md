---
feature: case-insensitive-upload-conflict
status: planned
created: 2026-07-02
---

# Feature Specification: Case-Insensitive Upload Conflict Handling

**Created**: 2026-07-02  
**Status**: Designed

## Context

The remote API rejects uploads with HTTP 400 when a file with the same name (case-insensitive)
already exists on the server. For example, if `bar.txt` is saved, uploading `Bar.txt` is rejected.

The API 400 response body:
```json
{
  "message": "string",
  "detail": [
    {
      "loc": ["string"],
      "msg": "string",
      "type": "string",
      "ctx": {}
    }
  ]
}
```

The `detail[0].ctx.path` field contains the conflicting server-side path.

### Scenario Table

| Worker                   | Online path exists | Case-insensitive match found | Current behavior          | Wanted behavior                                                   |
|--------------------------|-------------------|------------------------------|---------------------------|-------------------------------------------------------------------|
| FileUploadWorker         | no                | no                           | upload                    | upload (unchanged)                                                |
| FileUploadWorker         | yes               | n/a                          | no upload with warning    | no upload with warning (unchanged)                                |
| FileUploadWorker         | no                | yes                          | API error (unhandled 400) | no upload with warning (mention case sensitivity)                 |
| ExistingFileUploadWorker | yes               | no                           | upload                    | upload (unchanged)                                                |
| ExistingFileUploadWorker | no                | n/a                          | no upload with warning    | no upload with warning (unchanged)                                |
| ExistingFileUploadWorker | yes               | yes                          | n/a                       | n/a — renames preserve exact paths, so this case cannot occur     |
| schematisation           | yes               | no                           | upload after confirm      | upload after confirm (unchanged)                                  |
| schematisation           | yes               | yes                          | API error (unhandled 400) | upload after confirm (same dialog, triggered via 400 ctx.path)    |
| schematisation           | no                | n/a                          | upload                    | upload (unchanged)                                                |

## User Scenarios & Testing

### User Story 1 — New file upload blocked by case-insensitive conflict (Priority: P1)

A user uploads a new file (e.g. `Upload.gpkg`) to a directory where `upload.gpkg` already exists.
The API returns a 400 with the conflicting path in `ctx.path`. The plugin shows a warning and does
not complete the upload, rather than silently failing with an unhandled error.

**Why this priority**: Prevents silent/confusing failure. Users need a clear explanation of why
their upload was blocked.

**Independent Test**: Covered by new e2e test `test_upload_case_conflict`.

**Acceptance Scenarios**:

1. **Given** `upload.gpkg` exists on the server, **When** the user uploads `Upload.gpkg`,
   **Then** a warning message is shown mentioning case sensitivity, and `file_upload_failed`
   is emitted; no new file appears on the server.

2. **Given** no file exists on the server, **When** the user uploads `upload.gpkg`,
   **Then** the upload completes normally (regression: unchanged behavior).

---

### User Story 2 — Schematisation upload handles case-insensitive conflict via confirm dialog (Priority: P2)

A user uploads a schematisation whose filename matches an existing server file
case-insensitively (e.g. server has `myschema.gpkg`, user uploads `MySchema.gpkg`).
Instead of failing silently, the plugin catches the 400, looks up the conflicting file
at `ctx.path`, and presents the same overwrite-confirm dialog as for exact-path conflicts.

**Why this priority**: Schematisation uploads are higher-stakes operations. The confirm dialog
gives the user control over whether to overwrite.

**Independent Test**: Manual test paths 3 & 4 below.

**Acceptance Scenarios**:

1. **Given** `myschema.gpkg` exists on the server, **When** the user uploads `MySchema.gpkg`
   and confirms the overwrite dialog, **Then** the file is uploaded to the original server path
   (`myschema.gpkg`).

2. **Given** `myschema.gpkg` exists on the server, **When** the user uploads `MySchema.gpkg`
   and cancels the overwrite dialog, **Then** no upload occurs and `file_upload_failed` is
   emitted.

3. **Given** `myschema.gpkg` exists on the server (exact match), **When** the user uploads
   `myschema.gpkg` and confirms, **Then** the upload proceeds (regression: unchanged behavior).

---

### Edge Cases

- The API 400 body is malformed or `ctx.path` is absent: treat as a generic upload failure
  (`failed` signal), not a case-conflict warning.
- Multi-file batch upload via `FileUploadWorker`: each file is uploaded independently;
  a case conflict on one file emits `case_conflict` for that file and moves to the next.
  `finished` is still emitted after all files are attempted (consistent with current batch
  behavior where individual failures do not abort the batch).
- `finish_file_upload()` (PUT) does not return a 400 case-conflict; only `start_file_upload()`
  (POST) does. No changes needed for the finish step.

## Requirements

### Functional Requirements

- **FR-001**: `start_file_upload()` in `api.py` MUST return the parsed error body on failure,
  not just `None`, so callers can inspect the 400 response.
- **FR-002**: `FileUploadWorker` MUST emit a `case_conflict` signal (carrying `ctx.path`) when
  `start_file_upload()` returns a 400 with a recognisable case-conflict error body.
- **FR-003**: When `case_conflict` is emitted by `new_file_upload_worker`, `loader.py` MUST
  show a warning via `communication.show_warn()` mentioning case sensitivity, then emit
  `file_upload_failed`.
- **FR-004**: When `case_conflict` is emitted by the `FileUploadWorker` used in the
  schematisation upload path, `loader.py` MUST fetch the file at `ctx.path` and present the
  same overwrite-confirm dialog as for exact-path conflicts.
- **FR-005**: If the user confirms overwrite in the schematisation conflict dialog, the upload
  MUST proceed via `ExistingFileUploadWorker` targeting the server-side path from `ctx.path`.
- **FR-006**: `ExistingFileUploadWorker` MUST NOT be modified; case conflicts cannot occur for
  it given that renames preserve exact paths on the server.

### Key Entities

- **`ctx.path`**: The server-side path of the conflicting file, returned in `detail[0].ctx.path`
  of the API 400 response. Used to look up the existing file and/or re-route the upload.
- **`case_conflict` signal**: A new `pyqtSignal(str)` on `FileUploadWorker` that carries
  `ctx.path`. Distinct from `warning` (passive message) and `failed` (hard error).

## Implementation Design

### Component 1 — `utils/api.py::start_file_upload`

**Current signature**: `start_file_upload(project_id, params) → dict | None`

**New signature**: `start_file_upload(project_id, params) → tuple[dict | None, dict | None]`

- Returns `(response, None)` on success.
- Returns `(None, error_body)` on failure, where `error_body` is `network_manager.content`
  (the parsed 400 JSON, or `None` if unparseable).

The `network_manager.post()` call already populates `_content` on 400 errors
(see `network_manager.py:187-191`). The fix is to surface that content.

### Component 2 — `workers/upload.py::FileUploadWorker`

1. **New signal**: `case_conflict = pyqtSignal(str)` (carries `ctx.path`).

2. **New module-level helper**:
   ```python
   def _extract_case_conflict_path(error: dict | None) -> str | None:
       try:
           return error["detail"][0]["ctx"]["path"]
       except (KeyError, IndexError, TypeError):
           return None
   ```

3. **Updated `upload_single_file()`**: Handle tuple return from `start_file_upload()`.
   If `conflict_path` is found, emit `case_conflict` instead of `failed`.

### Component 3 — `loader.py` (regular file upload path)

In `initialize_new_file_upload_worker()`:
- Connect `new_file_upload_worker.case_conflict` to `_on_upload_case_conflict()`.

New method `_on_upload_case_conflict(conflict_path: str)`:
```
show_warn: "File not uploaded: a file named '<name>' already exists on the server.
            File names are case-sensitive."
emit file_upload_failed("")
```

### Component 4 — `loader.py` (schematisation upload path)

In `on_download_schematisation_finished()`:
- Connect `worker.case_conflict` to `_handle_schematisation_case_conflict()`.

New method `_handle_schematisation_case_conflict(project, online_dir, local_path, conflict_path)`:
1. Fetch `file = get_tenant_project_file(project["id"], {"path": conflict_path})`.
2. Show the same `communication.ask()` confirm dialog as the existing file-exists branch
   (lines 841-844 of `loader.py`).
3. If confirmed: create `ExistingFileUploadWorker(project, file, local_path)` with
   `file_overwrite = True` and start it with the same signal connections.
4. If declined: emit `file_upload_failed("")`.

### Component 5 — E2E test

**New test**: `e2e/test_api.py::test_upload_case_conflict`

**New fixture file**: `e2e/data/Upload.gpkg` (copy of `upload.gpkg` with capital U)

**Flow**:
1. Open project, upload `upload.gpkg` → wait for `file_upload_finished`.
2. Upload `Upload.gpkg` → dismiss the warning `QMessageBox` via `make_modal_handler`.
3. Assert `file_upload_failed` is emitted (not `file_upload_finished`).
4. Assert `Upload.gpkg` is not present in the files browser model.
5. Assert `upload.gpkg` is still present.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Uploading a case-variant filename shows a user-readable warning within the normal
  upload response time (no hang, no silent failure).
- **SC-002**: The new e2e test `test_upload_case_conflict` passes in CI.
- **SC-003**: All existing e2e upload tests continue to pass (no regressions).
- **SC-004**: Schematisation upload with a case-variant conflict presents the overwrite-confirm
  dialog and completes successfully when confirmed.

## Manual Testing Paths

1. Upload new file where server has a case-variant → warning shown, no upload *(e2e covered)*
2. Upload new file where no conflict exists → uploads normally *(existing `test_upload`)*
3. Schematisation upload where server has a case-variant → confirm → accept → uploads
4. Schematisation upload where server has a case-variant → confirm → decline → no upload
5. Schematisation upload where server has exact path match → existing confirm still works *(regression)*
