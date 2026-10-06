---
feature: case-insensitive-upload-conflict
status: planned
created: 2026-07-02
chunk_size: medium
total_tasks: 5
estimated_lines: 180
---

# Case-Insensitive Upload Conflict Handling — Tasks

## Overview

Handle the API's HTTP 400 rejection when a file with the same name (different case) already
exists on the server. Fixes `start_file_upload()` to surface the error body, adds a
`case_conflict` signal to `FileUploadWorker`, and wires up appropriate responses in `loader.py`
for both regular file uploads (warn + abort) and schematisation uploads (confirm dialog).

The e2e test is written first so it can be run manually to confirm failure before the fix lands.

---

## Phase 1: E2E test (write early — expected to fail until Phase 3 is done)

#### Task T001: E2E test fixture + `test_upload_case_conflict`
- **Estimate:** ~50 lines
- **Files:**
  - `e2e/test_api.py`
  - `e2e/data/Upload.gpkg` (copy of `upload.gpkg`, capital U)
- **Description:**
  Add `test_upload_case_conflict()` to the e2e test suite:
  1. Open project, upload `upload.gpkg` → wait for `file_upload_finished`.
  2. Upload `Upload.gpkg` (case-variant) → dismiss the warning `QMessageBox` via
     `make_modal_handler` → assert `file_upload_failed` is emitted (not `file_upload_finished`).
  3. Assert `Upload.gpkg` is **not** present in the files browser model.
  4. Assert `upload.gpkg` is still present in the files browser model.

  Create `e2e/data/Upload.gpkg` as a copy of `e2e/data/upload.gpkg`.
- **Depends on:** None
- **Acceptance:** Test exists and is runnable. It is expected to **fail** at this point because
  the 400 is not yet handled gracefully.

---

## Phase 2: Foundation

#### Task T002: Fix `start_file_upload()` return signature
- **Estimate:** ~20 lines
- **Files:**
  - `rana_qgis_plugin/utils/api.py`
  - `rana_qgis_plugin/workers/upload.py` (unpack tuple at call site, keep compiling)
- **Description:**
  Change `start_file_upload()` to return a tuple:
  - `(response, None)` on success
  - `(None, error_body)` on failure, where `error_body` is `network_manager.content`
    (already populated for 400 errors by `network_manager.py:187-191`)

  Update the call site in `upload.py:84` to unpack the tuple. At this stage just keep
  existing behaviour: treat `None` response as before (full signal handling comes in T003).
- **Depends on:** None
- **Acceptance:** Unit tests pass (`docker compose run --rm qgis pytest -v tests`).
  Plugin still compiles without errors.

---

## Phase 3: US1 — FileUploadWorker case-conflict signal + loader wiring

#### Task T003: `FileUploadWorker` helper + `case_conflict` signal
- **Estimate:** ~40 lines
- **Files:**
  - `rana_qgis_plugin/workers/upload.py`
- **Description:**
  1. Add module-level helper:
     ```python
     def _extract_case_conflict_path(error: dict | None) -> str | None:
         try:
             return error["detail"][0]["ctx"]["path"]
         except (KeyError, IndexError, TypeError):
             return None
     ```
  2. Add `case_conflict = pyqtSignal(str)` to `FileUploadWorker`.
  3. Update `upload_single_file()` to handle the tuple from `start_file_upload()`:
     if `_extract_case_conflict_path(error)` returns a path → emit `case_conflict(path)`;
     otherwise → emit `failed("Failed to initiate file upload.")`.
- **Depends on:** T002
- **Acceptance:** Unit tests pass. `case_conflict` signal is emitted (not `failed`) when
  the error body contains `detail[0].ctx.path`.

#### Task T004: Wire `case_conflict` in `loader.py` — regular upload path
- **Estimate:** ~25 lines
- **Files:**
  - `rana_qgis_plugin/loader.py`
- **Description:**
  In `initialize_new_file_upload_worker()`, connect:
  ```python
  self.new_file_upload_worker.case_conflict.connect(self._on_upload_case_conflict)
  ```
  Add new method `_on_upload_case_conflict(conflict_path: str)`:
  ```python
  self.communication.show_warn(
      f"File not uploaded: a file named '{Path(conflict_path).name}' already exists "
      f"on the server. File names are case-sensitive."
  )
  self.file_upload_failed.emit("")
  ```
- **Depends on:** T003
- **Acceptance:** `test_upload_case_conflict` (T001) now **passes**. Manual test path 1
  (upload case-variant → warning shown, no upload) works.

---

## Phase 4: US2 — Schematisation case-conflict confirm dialog

#### Task T005: Wire `case_conflict` in `loader.py` — schematisation upload path
- **Estimate:** ~45 lines
- **Files:**
  - `rana_qgis_plugin/loader.py`
- **Description:**
  In `on_download_schematisation_finished()`, connect:
  ```python
  worker.case_conflict.connect(
      lambda conflict_path: self._handle_schematisation_case_conflict(
          project, online_dir, local_path, conflict_path
      )
  )
  ```
  Add new method `_handle_schematisation_case_conflict(project, online_dir, local_path, conflict_path)`:
  1. Fetch `file = get_tenant_project_file(project["id"], {"path": conflict_path})`.
  2. Show same `communication.ask()` confirm dialog as the existing file-exists branch
     (same wording as `loader.py:841-844`).
  3. If confirmed: create `ExistingFileUploadWorker(project, file, local_path)` with
     `file_overwrite = True`, connect same signals as the existing branch, and start it.
  4. If declined: `self.communication.clear_message_bar()` + `self.file_upload_failed.emit("")`.
- **Depends on:** T003
- **Acceptance:** Manual test paths 3 & 4 (schematisation upload with case-variant conflict,
  accept and decline). Manual test path 5 (exact-path conflict still shows confirm dialog —
  regression).

---

## Dependencies & Execution Order

```
T001 (e2e test, fails)
T002 (api.py signature fix)   ← no dep, can start alongside T001
  └── T003 (worker signal)
        └── T004 (loader: regular path)   ← T001 now passes
        └── T005 (loader: schematisation) ← parallel with T004
```

T004 and T005 both depend on T003 but touch different methods in `loader.py` — they can be
written in the same session but should be committed separately for review clarity.

---

## Manual Testing Paths

1. Upload new file where server has a case-variant → warning shown, no upload *(e2e: T001)*
2. Upload new file where no conflict exists → uploads normally *(existing `test_upload`)*
3. Schematisation upload, case-variant conflict → confirm → accept → uploads *(manual)*
4. Schematisation upload, case-variant conflict → confirm → decline → no upload *(manual)*
5. Schematisation upload, exact-path conflict → existing confirm dialog works *(regression)*

---

## Progress

- [x] T001: E2E test fixture + `test_upload_case_conflict` (write early, expected to fail)
- [x] T002: Fix `start_file_upload()` return signature
- [x] T003: `FileUploadWorker` helper + `case_conflict` signal
- [x] T004: Wire `case_conflict` in `loader.py` — regular upload path
- [x] T005: Wire `case_conflict` in `loader.py` — schematisation upload path
