---
feature: threedi-api-request-logging
status: completed
created: 2026-11-02
chunk_size: medium
total_tasks: 3
estimated_lines: 180
---

# ThreeDi API Request Logging Tasks

## Overview

Implements logging of ThreeDi API HTTP request attempts to QGIS's Log Messages
panel ("Rana" category), by wrapping the transport request method of the
`ThreediApi` client instance — without modifying the `threedi-api-client`
package. The intended final behavior is opt-in.

**Deliberate sequencing**: During development, Tasks 1-2 install the logger
unconditionally because no setting exists yet. The engineer can observe it
under normal plugin use and confirm it's useful, not noisy, and never leaks
secrets. Task 3 — adding the QgsSettings toggle (default `False`) that makes
logging opt-in — is deliberately last, and should only be started once
Tasks 1-2 have been lived with and are judged satisfactory. Default-on is a
development phase only, not the intended shipped behavior.

See `design.md` for the full design rationale and
`.minispec/knowledge/decisions/20261102-1147-threedi-api-request-logging.md`
for the options considered.

## Task List

### Phase 1: Default-on logging (no setting yet)

#### Task 1: Request-summary and redaction helpers
- **Estimate:** ~50 lines
- **Files:**
  - `rana_qgis_plugin/simulation/threedi_api_logging.py` (new)
  - `tests/test_threedi_api_logging.py` (new)
- **Description:**
  - `redact_query_params(params: Sequence[tuple[str, Any]] | None)`: returns
    a copy with values
    replaced by `"***"` for any key containing a sensitive term
    (case-insensitive): `token`, `password`, `key`, `secret`, `authorization`.
    The type hint should reflect the sequence of `(name, value)` pairs used by
    the inspected API client's transport; mappings are not needed.
  - `build_request_summary(method: str, url: str, query_params: Sequence[tuple[str, Any]] | None) -> str`:
    returns a single-line string like `"GET https://host/api/path params={...}"`,
    redacting sensitive values in both the separately supplied params and
    query string embedded in `url` before formatting. No headers, no body,
    ever.
  - Keep formatting/redaction logic isolated from QGIS logging so it can be
    unit-tested independently.
- **Depends on:** None
- **Acceptance:**
  - Unit tests cover: no params, params with no sensitive keys, params with
    sensitive keys (including substring matches and mixed case), sensitive
    query values embedded in the URL, and confirm raw sensitive values never
    appear in the output string.

---

#### Task 2: Transport wrapper + wire into the personal-token client factory (default-on)
- **Estimate:** ~90 lines
- **Files:**
  - `rana_qgis_plugin/simulation/threedi_api_logging.py` (extend)
  - `rana_qgis_plugin/simulation/threedi_calls.py` (edit personal-token factory)
  - `tests/test_threedi_api_logging.py` (extend)
- **Description:**
  - Add `install_request_logger(api_client) -> None` to
    `threedi_api_logging.py`:
    - Locate the transport request method via
      `api_client._client.rest_client.request`.
    - Wrap it with a function that:
      1. Builds the request summary via Task 1's helper and logs it at
         `Qgis.MessageLevel.Info` under the `"Rana"` category (use
         `QgsMessageLog.logMessage(msg, PLUGIN_NAME, level)` — import
         `PLUGIN_NAME` from `rana_qgis_plugin.constant`).
      2. Calls the original method.
      3. On exception, logs a `Qgis.MessageLevel.Warning` line referencing
         the same summary and exception type; include `ApiException.status`
         when available. Do not log raw exception text, reason, headers, or
         response body. Re-raise the original exception unchanged.
    - Fail open around diagnostics: if summary construction or an Info log
      emission fails, still call the original transport. If transport raises,
      attempt the Warning log but ensure logging failure never replaces the
      original transport exception.
    - Replace the instance attribute with the wrapped function
      (`api_client._client.rest_client.request = wrapped`).
    - Wrap the whole installation in a defensive `try/except` (e.g.
      `AttributeError`): if the expected attribute chain doesn't exist, log a
      single warning via `QgsMessageLog.logMessage` and return without
      raising — the API client must remain fully usable either way.
  - In `get_api_client_with_personal_api_token()` in
    `simulation/threedi_calls.py`, call `install_request_logger(api_client)`
    unconditionally after client construction and before returning it. No
    setting check yet.
- **Depends on:** Task 1
- **Acceptance:**
  - Unit tests use a fake/mock object standing in for
    `api_client._client.rest_client` to verify:
    - A successful call logs one Info line and returns the original result
      unchanged.
    - A call that raises logs an Info line (attempt) then a Warning line
      (failure) with exception type and optional API status, without raw
      exception text, and re-raises the original exception unchanged.
    - Missing attribute chain (e.g. `_client` absent) does not raise from
      `install_request_logger` itself.
    - Summary formatting or Info/Warning log emission failures do not block
      transport invocation, alter its return value, or replace its exception.
  - Unit test: `get_api_client_with_personal_api_token()` installs the wrapper
    on the client it constructs during the development phase.
  - Manual check: open the simulation overview or another ThreeDi-backed
    panel in QGIS, confirm log lines appear in the Rana log category showing
    method/path/params, with no raw secrets visible.

**Checkpoint — stabilization period:** Live with this default-on behavior
across normal plugin use before starting Task 3. Confirm: log volume is
reasonable, lines are useful for diagnosing issues, and no sensitive values
ever leak. Only move to Task 3 once satisfied.

---

### Phase 2: Gate behind the settings toggle (final task)

#### Task 3: Add settings toggle, gate the wrapper, default off
- **Estimate:** ~40 lines
- **Files:**
  - `rana_qgis_plugin/utils/settings.py` (add accessor)
  - `rana_qgis_plugin/simulation/threedi_calls.py` (make the Task 2 call conditional)
  - `README.md` (document the hidden setting and how to enable it)
  - `tests/test_utils_settings.py` (extend)
  - `tests/test_threedi_api_logging.py` (extend factory coverage)
- **Description:**
  - Add `get_log_threedi_api_requests() -> bool` to `utils/settings.py`,
    reading `QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/log_threedi_api_requests", False, type=bool)`,
    following the exact pattern of `get_use_plugin_excepthook()`.
  - In `get_api_client_with_personal_api_token()`, change the unconditional
    `install_request_logger(api_client)` call from Task 2 to:
    `if get_log_threedi_api_requests(): install_request_logger(api_client)`.
  - Add the setting name to `get_advanced_settings()` so it appears in the
    settings dialog's read-only Advanced Settings section when set.
  - Update the README to document the QgsSettings key, default-off
    behavior, and how developers can enable it for diagnostics.
  - This task is scoped strictly to adding the setting and flipping the
    default from on to off-by-default-with-opt-in. No logging-behavior
    changes (verbosity, redaction rules, log level) are bundled in here —
    if the stabilization period surfaced desired tweaks, handle those as a
    separate, preceding change to Task 2's code first.
- **Depends on:** Task 2 (and the stabilization checkpoint above)
- **Acceptance:**
  - Unit test: setting unset/False →
    `get_api_client_with_personal_api_token()` does not install the wrapper
    (e.g. assert `install_request_logger` not called, via mock).
  - Unit test: setting True → wrapper is installed (assert called).
  - Unit test: `get_advanced_settings()` includes the setting when present.
  - Manual check: with the setting left unset, confirm no request-attempt
    log lines appear during normal use; set
    `Rana/log_threedi_api_requests=true` via the Python console
    (`QgsSettings().setValue(...)`) and confirm logging resumes.

## Notes

- All three tasks touch `rana_qgis_plugin/simulation/threedi_api_logging.py`
  and/or `rana_qgis_plugin/simulation/threedi_calls.py` — no parallelization
  opportunities; work through them in order.
- `get_api_client()` and `get_api_client_with_tokens()` in
  `simulation/threedi_calls.py` are intentionally left uninstrumented — they
  are unused anywhere in the plugin today. Out of scope for this feature.
- The transport hook point (`_client.rest_client.request`) reflects the
  installed `threedi-api-client` 5.0.5 at design time. If the installed
  version changes and the attribute chain no longer matches,
  `install_request_logger`'s defensive try/except must keep the plugin
  working — this should be covered by Task 2's "missing attribute chain"
  test.

## Progress

- [x] Task 1: Request-summary and redaction helpers
- [x] Task 2: Transport wrapper + wire into personal-token factory (default-on)
- [x] Task 3: Add settings toggle, gate the wrapper, default off
