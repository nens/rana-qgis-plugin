---
type: decision
id: 20261102-1147-threedi-api-request-logging
date: 2026-11-02
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/api_logging.py
  - rana_qgis_plugin/simulation/threedi_calls.py
  - rana_qgis_plugin/utils/settings.py
  - rana_qgis_plugin/workers/upload.py
  - rana_qgis_plugin/simulation/utils.py
  - rana_qgis_plugin/simulation/workers.py
tags: [debugging, logging, threedi-api-client, network, uploads]
participants: [engineer, implementation-agent]
---

# Log API request and upload attempts via transport-level wrappers

## Context

Rana API calls use `NetworkManager` (Qt Network / `QgsNetworkAccessManager`),
which is visible to QGIS's built-in network debugging tools. ThreeDi API
calls go through the external `threedi-api-client` package, which uses its
own `urllib3`-based transport and is entirely invisible to those tools.

We investigated bridging the two transports so ThreeDi calls would appear
natively in QGIS's network tools, but this would require adapting between two
different networking APIs (threading model, timeouts, redirects, TLS,
response handling) — a disproportionate effort for a debugging aid, and it
would require depending on deep internals of `threedi-api-client`.

Instead we want a lightweight way to see HTTP request *attempts* — including
ones that fail before a response is received — surfaced through QGIS's
existing Log Messages panel, without modifying the `threedi-api-client`
package. The ThreeDi REST API logger (Tasks 1-3) was built first, initially
unconditional during development, then gated behind the setting
`Rana/log_threedi_api_requests` (default `False`).

**Extended scope**: once the REST logger existed, we identified that Rana and
ThreeDi *file upload* paths are invisible to both QGIS's network debugger and
the ThreeDi REST logger, because they bypass both transports:

- `rana_qgis_plugin/workers/upload.py:177` and
  `rana_qgis_plugin/simulation/utils.py:282` call `requests.put()` directly on
  a presigned upload URL returned by a prior (already-logged) API call.
- `rana_qgis_plugin/simulation/workers.py:1299,1340` call
  `threedi_api_client.files.upload_file()`, a standalone helper that does not
  use a `ThreediApi` instance at all — it opens its own `urllib3.PoolManager`
  (or accepts one via its `pool=` parameter).

This decision record now covers both the REST logger (implemented) and this
upload-logging extension.

In the inspected version of `threedi_api_client` (5.0.5):

```
ThreediApi._client.rest_client.request(method, url, query_params=..., ...)
  -> urllib3.PoolManager.request(...)

threedi_api_client.files.upload_file(url, file_path, pool=None, ...)
  -> pool = pool or get_pool()  # urllib3.PoolManager(retries=Retry(3, backoff_factor=1.0))
  -> pool.request("PUT", url, ...)
```

`RESTClientObject.request(...)` and `upload_file()`'s `pool.request(...)` call
are each the last point before control passes to `urllib3`. Logging
immediately before these calls captures intent-to-send, independent of
whether the network call ultimately succeeds.

## Options Considered

### Option 1: Log at the `ThreediCalls` method level (e.g. decorate `fetch_simulations`, etc.)

- Simple, no dependency on client internals
- Doesn't capture pagination sub-calls or internal auth/token-refresh requests
  distinctly from the "main" call
- Doesn't reliably show HTTP method/URL — that information isn't available at
  this layer without re-deriving it
- Wouldn't catch requests that fail before entering a `ThreediCalls` method
  wrapper in some edge cases (e.g. errors raised during client construction)
- Does not address uploads at all, since they are not `ThreediCalls` methods

### Option 2: Wrap the transport (`RESTClientObject.request`, and separately, `requests.put`/`upload_file`'s pool) via monkey-patching/injection

- Captures the actual HTTP method, URL, and query params for every REST
  request the client sends, including pagination and internal auth calls
- Captures requests that fail before a response (logs before calling through)
- For uploads, uses each transport's own extension point: wrapping
  `requests.put()` directly for direct-PUT call sites, and injecting a
  logging-enabled `urllib3.PoolManager` via `upload_file(pool=...)` for the
  file-helper call sites — since these are genuinely different transports,
  requiring two separate wrapper mechanisms rather than one shared hook
- Touches client/library internals (`_client.rest_client`, `urllib3.PoolManager`),
  so each wrapper must be defensive and tolerant of library changes
- Fully contained in plugin code — no changes to `threedi-api-client`

### Option 3: Subclass `RESTClientObject` and inject it via client configuration

- Would be a "cleaner" OOP approach if the client supported pluggable REST
  client classes
- Not confirmed to be supported by `threedi-api-client`'s configuration
  surface; would require more invasive attribute manipulation than Option 2
  for equivalent behavior
- Does not address uploads, which don't use `RESTClientObject` at all
- No clear advantage over Option 2 given the uncertainty

## Decision

We chose **Option 2**, applied per-transport:

1. **REST API logging** (implemented, Tasks 1-3): monkey-patch
   `_client.rest_client.request` on each `ThreediApi` instance returned by
   `get_api_client_with_personal_api_token()`.
2. **Direct-PUT upload logging** (this extension, Task 4): wrap
   `requests.put()` at the two direct call sites
   (`workers/upload.py:177`, `simulation/utils.py:282`) with a shared helper
   function in the relocated logging module.
3. **`upload_file()` upload logging** (this extension, Task 5): construct a
   logging-enabled `urllib3.PoolManager` and pass it as the `pool=` argument
   at the two `upload_file()` call sites (`simulation/workers.py:1299,1340`),
   since `upload_file()` has no other extension point and does not use a
   `ThreediApi` instance.

Specifically:

- **Setting rename**: the setting `Rana/log_threedi_api_requests` is renamed
  to `Rana/log_api_requests` in this extension, since it now gates upload
  logging in addition to REST logging. No compatibility alias is kept; the
  old key was never part of a shipped release. It follows the existing
  `use_plugin_excepthook` pattern and is included in `get_advanced_settings()`
  so its value is visible (read-only) in the Advanced Settings section.
- **Module relocation**: the logging module moves from
  `rana_qgis_plugin/simulation/threedi_api_logging.py` to
  `rana_qgis_plugin/utils/api_logging.py`, since it now covers a Rana upload
  path (`workers/upload.py`) in addition to ThreeDi paths, so it no longer
  belongs under `simulation/`. The corresponding test file is renamed
  `tests/test_utils_api_logging.py`.
- Only `get_api_client_with_personal_api_token()` is wired for REST logging,
  because the other two factories in `simulation/threedi_calls.py`
  (`get_api_client` and `get_api_client_with_tokens`) are unused in the
  plugin.
- The REST wrapper logs an `Info`-level message to the QGIS "Rana" log
  category (via the same mechanism as `UICommunication.log_msg`) with the
  HTTP method, host+path, and redacted query params, immediately before
  calling through to the original transport method. On exception, it logs a
  `Warning`-level message with the exception type (and `ApiException.status`
  when available) — never raw exception text, reason, headers, or response
  body — then re-raises unchanged.
- **Upload summaries never include the query string**, not even redacted:
  presigned upload URLs can embed signatures or credentials directly in the
  query string, so the entire query string is omitted rather than attempting
  to redact specific parameter names (as is done for REST query params).
  Headers and file contents are never logged for uploads either.
- The `upload_file()` logging pool must be constructed with the same retry
  policy the helper would otherwise use by default
  (`Retry(3, backoff_factor=1.0)`, matching
  `threedi_api_client.files.get_pool()`), so upload resilience is unchanged
  whether or not logging is enabled.
- Sensitive REST query parameter names containing `token`, `password`, `key`,
  `secret`, or `authorization` (case-insensitive) have their values redacted
  as `***`; this redaction behavior is unchanged from the original REST
  logger and does not apply to upload summaries (which omit the query string
  entirely instead).
- All REST requests the ThreeDi transport sends are logged, including
  internal auth/token-refresh requests — we do not attempt to filter to only
  "application-level" calls, since that distinction isn't reliably available
  at the transport layer.
- All wrappers (REST and upload) fail safely at installation time and fail
  open at call time: if a wrapper cannot be installed, or if building/logging
  a summary raises, the plugin continues to function normally and the
  original transport call still proceeds with unchanged arguments, return
  value, and exceptions.

## Consequences

### Positive

- ✅ Request attempts are logged for ThreeDi REST calls and for the two
  upload transports (`requests.put()` and `upload_file()`'s pool), closing
  the previously-identified gap where only the upload-*creating* API call
  (not the actual file transfer) was visible.
- ✅ No changes to the `threedi-api-client` package.
- ✅ A single generic setting (`Rana/log_api_requests`) controls all of this,
  discoverable via the existing read-only Advanced Settings display.
- ✅ Any caller of `get_api_client_with_personal_api_token()` receives a
  wrapped client; requests include pagination without instrumenting each API
  method individually.
- ✅ Upload retry/backoff/progress-callback behavior is explicitly preserved,
  so enabling logging cannot change upload resilience.

### Negative

- ⚠️ Relies on internal attributes of the installed `threedi-api-client`
  version (`_client.rest_client.request`, `upload_file()`'s `pool=` contract);
  a future client upgrade could silently stop logging if these change.
  Mitigated by fail-safe installation (never blocks usage).
- ⚠️ Does not confirm requests were actually transmitted/received by the
  server — only that they were handed to the transport. This is a known and
  accepted limitation, not a correctness gap for this feature's purpose.
- ⚠️ Does not surface individual `urllib3` retry attempts, only the logical
  request/upload as seen by the caller.
- ⚠️ Omitting the entire query string from upload logs means legitimate,
  non-sensitive query parameters (if any) are also hidden — considered an
  acceptable tradeoff given presigned-URL risk.

### Neutral

- The REST logger was unconditional during its own development/stabilization
  phase; this is historical and does not apply to the upload loggers added in
  this extension, which are opt-in from day one.
- This remains a developer/support-facing diagnostic feature; the setting's
  only discoverability is the existing read-only Advanced Settings display.
- Bridging ThreeDi calls into QGIS's native network debugging tools remains
  out of scope and would be a separate, much larger effort if ever pursued.
- `processing/label_dwf.py`'s upload/download and all file *downloads*
  remain explicitly out of scope for this logging feature.

## Code References

- REST client construction/integration point:
  `rana_qgis_plugin/simulation/threedi_calls.py:get_api_client_with_personal_api_token()`
- Direct-PUT upload call sites:
  `rana_qgis_plugin/workers/upload.py:177`,
  `rana_qgis_plugin/simulation/utils.py:282`
- `upload_file()` call sites:
  `rana_qgis_plugin/simulation/workers.py:1299` (`upload_sqlite_task`),
  `:1340` (`upload_raster_task`)
- Relocated logging module:
  `rana_qgis_plugin/utils/api_logging.py` (was
  `rana_qgis_plugin/simulation/threedi_api_logging.py`)
- Settings pattern to follow: `rana_qgis_plugin/utils/settings.py:138-141`
  (`get_use_plugin_excepthook`)
- Logging mechanism to reuse: `rana_qgis_plugin/communication.py:120-134`
  (`UICommunication.log_msg` / `QgsMessageLog.logMessage`)
- Transport hook points (installed version 5.0.5):
  `threedi_api_client.openapi.rest.RESTClientObject.request`, reached via
  `ThreediApi._client.rest_client.request`;
  `threedi_api_client.files.upload_file(pool=...)`, whose default pool is
  `threedi_api_client.files.get_pool()` → `urllib3.PoolManager(retries=Retry(3, backoff_factor=1.0))`

## Related Decisions

None yet — this is the first decision record for this feature (originally
scoped to REST logging only, now extended to cover upload logging).

## Notes

Manual testing should cover:
- ThreeDi API actions (e.g. opening the simulation overview) with
  `Rana/log_api_requests` enabled and disabled.
- A Rana project-file upload via `workers/upload.py`.
- A ThreeDi `requests.put()` upload via `simulation/utils.py` (e.g. boundary
  condition or initial waterlevel upload in the simulation wizard).
- A ThreeDi schematisation SQLite/GeoPackage upload and a raster upload via
  `simulation/workers.py` (`upload_file()` path), confirming progress
  callbacks and retries still behave normally.
- Simulating a network failure (e.g. invalid host) for at least one REST and
  one upload path, to confirm the Warning-level failure log appears and the
  original exception still propagates.
