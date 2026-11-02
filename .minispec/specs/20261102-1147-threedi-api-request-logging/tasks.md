---
feature: threedi-api-request-logging
status: in_progress
created: 2026-11-02
chunk_size: medium
total_tasks: 5
estimated_lines: 300
---

# API Request and Upload Attempt Logging Tasks

## Overview

Implements logging of ThreeDi API HTTP request attempts and file upload
attempts (Rana and ThreeDi) to QGIS's Log Messages panel ("Rana" category),
without modifying the `threedi-api-client` package. Final behavior is opt-in
via `Rana/log_api_requests`.

**Status of Tasks 1-3**: Already implemented and committed on this branch.
They built the ThreeDi REST API logger under the (now superseded) setting
name `Rana/log_threedi_api_requests`.

**This extension (Tasks 4-5)**:
- Renames the setting to the generic `Rana/log_api_requests` and lists it in
  `get_advanced_settings()`.
- Relocates the logging module from
  `rana_qgis_plugin/simulation/threedi_api_logging.py` to
  `rana_qgis_plugin/utils/api_logging.py`, since it now covers a Rana upload
  path, not just ThreeDi.
- Adds upload-attempt logging for direct `requests.put()` calls (Task 4) and
  for `threedi_api_client.files.upload_file()` calls via its `pool=` argument
  (Task 5) — these use different transports, so they're split into separate
  tasks.

See `design.md` for the full design rationale and
`.minispec/knowledge/decisions/20261102-1147-threedi-api-request-logging.md`
for the options considered.

## Task List

### Phase 1: ThreeDi REST API request logging (completed)

#### Task 1: Request-summary and redaction helpers — done
- **Estimate:** ~50 lines
- **Files:**
  - `rana_qgis_plugin/simulation/threedi_api_logging.py` (new, since relocated
    in Task 4)
  - `tests/test_threedi_api_logging.py` (new, since renamed in Task 4)
- Implemented `redact_query_params()` and `build_request_summary()`.

#### Task 2: Transport wrapper + wire into the personal-token client factory — done
- **Estimate:** ~90 lines
- Implemented `install_request_logger()`, wired into
  `get_api_client_with_personal_api_token()` (initially unconditional for
  stabilization).

#### Task 3: Add settings toggle, gate the wrapper, default off — done
- **Estimate:** ~40 lines
- Added `get_log_threedi_api_requests()` / `Rana/log_threedi_api_requests`
  (default `False`), gated the REST logger behind it, and listed it in
  `get_advanced_settings()`.

---

### Phase 2: Rename setting, relocate module, add direct-PUT upload logging

#### Task 4: Rename setting, relocate module, log direct `requests.put()` uploads
- **Estimate:** ~80 lines
- **Files:**
  - `rana_qgis_plugin/simulation/threedi_api_logging.py` → **move/rename to**
    `rana_qgis_plugin/utils/api_logging.py`
  - `tests/test_threedi_api_logging.py` → **move/rename to**
    `tests/test_utils_api_logging.py`
  - `rana_qgis_plugin/utils/settings.py` (rename accessor, add to
    `get_advanced_settings()`)
  - `rana_qgis_plugin/simulation/threedi_calls.py` (update import, use
    renamed accessor)
  - `rana_qgis_plugin/workers/upload.py` (wrap the `requests.put()` call)
  - `rana_qgis_plugin/simulation/utils.py` (wrap the `requests.put()` call)
  - `tests/test_utils_settings.py` (rename test coverage for the setting)
  - `README.md` (update setting name/instructions)
- **Description:**
  - Move `simulation/threedi_api_logging.py` to `utils/api_logging.py`
    unchanged in content; update the one import in `threedi_calls.py`.
    Rename `tests/test_threedi_api_logging.py` to
    `tests/test_utils_api_logging.py` and fix its import path.
  - In `utils/settings.py`: rename `get_log_threedi_api_requests()` to
    `get_log_api_requests()`, reading
    `QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/log_api_requests", False, type=bool)`.
    Add `"log_api_requests"` to the `settings_names` list in
    `get_advanced_settings()`.
  - In `threedi_calls.py`: update the import and the conditional call to use
    `get_log_api_requests()`.
  - In `utils/api_logging.py`, add a new function
    `logged_put(url: str, **kwargs) -> requests.Response` (or similarly
    named) that:
    1. Builds a summary string containing only `PUT` + the URL's host/path
       (using `urllib.parse.urlsplit`, discarding `.query` entirely — do not
       reuse the REST redaction helper here, since upload query strings must
       never appear, not even redacted).
    2. Logs the summary at `Qgis.MessageLevel.Info` via the same
       `QgsMessageLog.logMessage(msg, PLUGIN_NAME, level)` mechanism as the
       REST logger, gated by `get_log_api_requests()`.
    3. Calls `requests.put(url, **kwargs)`.
    4. On exception, logs a `Qgis.MessageLevel.Warning` line with the
       exception type (no raw exception text), then re-raises unchanged.
    5. Fails open: if step 1/2 raises, still perform step 3 and return/raise
       its result unchanged.
  - In `workers/upload.py:177`, replace `requests.put(upload_url, data=file)`
    with the new helper, passing through the same arguments.
  - In `simulation/utils.py:282`, replace `requests.put(upload.put_url, data=file)`
    with the new helper, passing through the same arguments.
  - Update README instructions for `Rana/log_api_requests`.
- **Depends on:** Task 3
- **Acceptance:**
  - Unit tests (in `tests/test_utils_api_logging.py`) verify:
    - `logged_put()` logs one Info line (method + host/path, no query string)
      before calling `requests.put()`, and returns its result unchanged, when
      logging is enabled.
    - `logged_put()` makes no log calls when `get_log_api_requests()` is
      `False`, and still calls `requests.put()` normally.
    - A query string present in the URL never appears in any logged message.
    - If `requests.put()` raises, a Warning line is logged (exception type
      only) and the original exception propagates unchanged.
    - Logging helper failures (e.g. patched to raise) do not prevent
      `requests.put()` from being called or change its result.
  - Unit tests (in `tests/test_utils_settings.py`) verify
    `get_log_api_requests()` reads/defaults correctly and
    `get_advanced_settings()` includes `log_api_requests` when set.
  - Manual check: with `Rana/log_api_requests=true`, perform one Rana project
    file upload and one ThreeDi upload that goes through
    `simulation/utils.py:upload_local_file()` (e.g. boundary condition or
    initial waterlevel upload in the simulation wizard); confirm log lines
    appear in the Rana log category with no query string or file contents.
    With the setting unset, confirm no such lines appear and uploads still
    succeed.

---

### Phase 3: Upload logging for `threedi_api_client.files.upload_file()`

#### Task 5: Logging-enabled pool for `upload_file()` uploads
- **Estimate:** ~70 lines
- **Files:**
  - `rana_qgis_plugin/utils/api_logging.py` (extend)
  - `rana_qgis_plugin/simulation/workers.py` (pass logging pool at two call
    sites)
  - `tests/test_utils_api_logging.py` (extend)
- **Description:**
  - In `utils/api_logging.py`, add a function
    `get_logging_pool() -> urllib3.PoolManager` (or similar) that:
    1. Returns a plain `urllib3.PoolManager(retries=urllib3.util.retry.Retry(3, backoff_factor=1.0))`
       (matching `threedi_api_client.files.get_pool()`'s defaults) when
       `get_log_api_requests()` is `False` — i.e. behaves exactly like not
       passing `pool=` at all.
    2. When `get_log_api_requests()` is `True`, returns a `PoolManager`
       subclass/wrapper whose `request()` method:
       - Logs an Info-level summary (method + host/path, no query string)
         before delegating to the real pool request.
       - On exception, logs a Warning-level line (exception type only) and
         re-raises unchanged.
       - Fails open around steps above; always delegates to the real
         request call with unchanged arguments.
       - Is constructed with the same `Retry(3, backoff_factor=1.0)` policy.
  - In `simulation/workers.py:1299` (`upload_sqlite_task`) and `:1340`
    (`upload_raster_task`), pass `pool=get_logging_pool()` to the existing
    `upload_file(...)` calls, alongside the existing `callback_func=` and
    other arguments — do not change any other call arguments.
- **Depends on:** Task 4 (reuses the relocated module and renamed setting)
- **Acceptance:**
  - Unit tests verify:
    - With logging disabled, `get_logging_pool()` returns a pool whose retry
      policy matches `Retry(3, backoff_factor=1.0)` and that performs
      requests with no extra log calls.
    - With logging enabled, a request through the pool logs one Info line
      (method + host/path, no query) before delegating, and returns the
      delegate's response unchanged.
    - An exception from the delegate pool's request is logged at Warning
      (exception type only) and re-raised unchanged.
    - The retry policy is unchanged between the logging and non-logging pool
      (same `Retry` configuration).
  - Manual check: with `Rana/log_api_requests=true`, upload a schematisation
    (SQLite/GeoPackage) and a raster via the upload wizard; confirm Info-level
    log lines appear for each PUT attempt, without query strings or file
    contents, and that the uploads still complete successfully (including
    their progress callback behavior). With the setting unset, confirm no
    such lines appear and uploads still succeed.

## Notes

- Tasks 4 and 5 both touch `rana_qgis_plugin/utils/api_logging.py` — do Task
  4 first (it performs the module relocation), then Task 5 extends the
  relocated module. No parallelization between them.
- `get_api_client()` and `get_api_client_with_tokens()` in
  `simulation/threedi_calls.py` remain intentionally uninstrumented — unused
  anywhere in the plugin.
- `processing/label_dwf.py`'s upload/download calls and all file *downloads*
  remain explicitly out of scope — see `design.md`'s Out of Scope section.
- The transport hook point for REST logging
  (`_client.rest_client.request`) reflects the installed `threedi-api-client`
  5.0.5 at design time; the defensive try/except around installation must
  keep the plugin working if this changes in a future dependency bump.
- The `upload_file()` pool hook point (`pool=` parameter) and its default
  retry policy (`Retry(3, backoff_factor=1.0)` via
  `threedi_api_client.files.get_pool()`) were confirmed against the installed
  `threedi-api-client` 5.0.5 package during design.

## Progress

- [x] Task 1: Request-summary and redaction helpers
- [x] Task 2: Transport wrapper + wire into personal-token factory
- [x] Task 3: Add settings toggle, gate the wrapper, default off
- [x] Task 4: Rename setting, relocate module, log direct `requests.put()` uploads
- [ ] Task 5: Logging-enabled pool for `upload_file()` uploads
</content>
