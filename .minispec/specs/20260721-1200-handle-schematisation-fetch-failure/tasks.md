---
feature: handle-schematisation-fetch-failure
status: completed
created: 2026-07-21
chunk_size: medium
total_tasks: 7
estimated_lines: 265
---

# Handle Schematisation Fetch Failure — Tasks

## Overview

Refactor `get_threedi_schematisation` to raise `FetchError` instead of returning `None`, and add `try/except FetchError` at all 11 call sites. Tasks are ordered to support incremental manual testing: first make the function always raise (surfacing all unguarded call sites), then fix call sites in UI-area batches, then restore correct error-only raising.

No unit tests are added — API mocking is not yet in scope for this codebase.

## Task List

### Foundation

#### Task 1: Make `get_threedi_schematisation` always raise `FetchError`
- **Estimate:** ~15 lines
- **Files:** `rana_qgis_plugin/utils/api.py`
- **Description:** Remove the `communication` parameter. Replace the function body with an unconditional `raise FetchError("always raise for testing", url, {})`. This makes every unguarded call site crash loudly, confirming which paths need fixing before any real logic is restored.
- **Depends on:** None
- **Acceptance:** Calling the function in any context raises `FetchError` immediately.

---

### Core: Add `try/except FetchError` — batch by UI area

#### Task 2: Fix `widgets/file_view.py` + `widgets/files_browser.py`
- **Estimate:** ~50 lines
- **Files:** `rana_qgis_plugin/widgets/file_view.py`, `rana_qgis_plugin/widgets/files_browser.py`
- **Description:** Both call sites already guard with `if schematisation:`. Replace the call + None-check with `try/except FetchError`, showing an error via `self.communication.show_error(...)` in the except block. Return early as before.
- **Depends on:** Task 1
- **Manual test paths:**
  - Navigate to a schematisation in the Files Browser
  - Select a schematisation → FileView loads
- **Acceptance:** Both paths show a user-facing error instead of crashing when API fails.

#### Task 3: Fix `widgets/utils_file_action.py` + `widgets/revisions_view.py`
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/widgets/utils_file_action.py`, `rana_qgis_plugin/widgets/revisions_view.py`
- **Description:** `utils_file_action.py` has an existing `if schematisation:` guard; replace with try/except. `revisions_view.py` is a latent bug (no guard); add try/except and return early.
- **Depends on:** Task 1
- **Manual test paths:**
  - Select a schematisation → click "Open in browser"
  - Select a schematisation → expand "Revisions" panel
- **Acceptance:** Both paths show a user-facing error instead of crashing when API fails.

#### Task 4: Fix `loader.py` — download + open-recursively (~line 414, ~521)
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/loader.py`
- **Description:** Both call sites have existing `if schematisation:` guards. Replace with try/except FetchError; return/emit early in the except block as each currently does on None.
- **Depends on:** Task 1
- **Manual test paths:**
  - Select a schematisation → click Download
  - Select multiple files including a schematisation → "Open projects recursively"
- **Acceptance:** Both paths show a user-facing error instead of crashing when API fails.

#### Task 5: Fix `loader.py` — model/export/delete actions (~line 775, ~786, ~893)
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/loader.py`
- **Description:** Three latent-bug call sites with no None guard. Wrap each in try/except FetchError and return early with an error message.
- **Depends on:** Task 1
- **Manual test paths:**
  - Select a schematisation → Actions → "Create 3Di model"
  - Select a schematisation → Actions → "Export schematisation"
  - Select a schematisation → Actions → "Delete 3Di model"
- **Acceptance:** All three paths show a user-facing error instead of crashing when API fails.

#### Task 6: Fix `loader.py` — simulation + upload revision (~line 940, ~1669)
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/loader.py`
- **Description:** Two latent-bug call sites with no None guard. Wrap each in try/except FetchError and return early with an error message.
- **Depends on:** Task 1
- **Manual test paths:**
  - Select a schematisation → Actions → "Start simulation"
  - Select a schematisation → Actions → "Upload revision"
- **Acceptance:** Both paths show a user-facing error instead of crashing when API fails.

---

### Completion

#### Task 7: Fix `get_threedi_schematisation` to only raise on real errors
- **Estimate:** ~20 lines
- **Files:** `rana_qgis_plugin/utils/api.py`
- **Description:** Replace the always-raise stub with the real implementation: make the network call, raise `FetchError` only when `status` is falsy, return the response on success. The `communication` parameter stays removed.
- **Depends on:** Tasks 2, 3, 4, 5, 6 (all call sites must be fixed first)
- **Manual test paths:** Full happy-path re-test of all 11 UI paths listed in design.md
- **Acceptance:** All 11 UI paths work normally; API failure shows a user-facing error at each path.

---

## Notes

- No unit tests are added in this fix — API mocking is not yet in scope.
- Tasks 2–6 can be done in any order relative to each other (all depend only on Task 1).
- Task 7 must come last — restoring correct behaviour only makes sense once all call sites are guarded.

## Progress

- [x] Task 1: Make `get_threedi_schematisation` always raise `FetchError`
- [x] Task 2: Fix `widgets/file_view.py` + `widgets/files_browser.py`
- [x] Task 3: Fix `widgets/utils_file_action.py` + `widgets/revisions_view.py`
- [x] Task 4: Fix `loader.py` — download + open-recursively
- [x] Task 5: Fix `loader.py` — model/export/delete actions
- [x] Task 6: Fix `loader.py` — simulation + upload revision
- [x] Task 7: Fix `get_threedi_schematisation` to only raise on real errors
