# Feature Specification: API Request and Upload Attempt Logging

**Created**: 2026-11-02
**Status**: Planned
**Branch**: feat_5343_api_logging
**Input**: Developer need to see ThreeDi API (threedi-api-client) HTTP request
attempts, plus file upload attempts to Rana and ThreeDi, in QGIS's
debugging/logging tools.

## Background

Rana API calls made via `NetworkManager` (Qt Network / `QgsNetworkAccessManager`)
are visible through QGIS's network debugging tools. ThreeDi API calls made via
the external `threedi-api-client` package are not, because that package uses
its own `urllib3`-based transport, entirely separate from QGIS's network stack.

This feature does not attempt to route ThreeDi API calls through QGIS's
network manager (a large transport-bridging effort, out of scope). Instead, it
adds a developer-facing log of HTTP request attempts, written to QGIS's
existing Log Messages panel under the "Rana" category. It covers:

1. ThreeDi REST API request attempts (already implemented — see Tasks 1-3)
2. File upload attempts to Rana and ThreeDi that bypass both `NetworkManager`
   and the ThreeDi REST client, because they transfer file bytes directly via
   `requests.put()` or `threedi_api_client.files.upload_file()` (this
   extension — Task 4)

Rana API requests made through `NetworkManager` remain visible via QGIS's
native network debugging tools and are **not** part of this feature. File
*downloads* and the DWF-labeling processing upload
(`processing/label_dwf.py`) are also out of scope — see Out of Scope.

**Rollout sequencing**: during development, the ThreeDi REST logger was
initially installed unconditionally (no setting yet) so the engineer could
evaluate it under normal plugin use. Task 3 then added the opt-in setting
`Rana/log_threedi_api_requests` (default `False`). This extension (Task 4)
**renames that setting to the more generic `Rana/log_api_requests`**, since it
now also gates upload-attempt logging, and lists it in
`get_advanced_settings()` so its value is visible (read-only) in the settings
dialog's Advanced Settings section. Upload-attempt logging is opt-in from its
first implementation — there is no default-on stabilization phase for it.

**Module relocation**: the logging helpers currently live in
`rana_qgis_plugin/simulation/threedi_api_logging.py`. Since this extension
adds logging for a Rana upload path (`workers/upload.py`) as well as ThreeDi
paths, the module no longer belongs under `simulation/`. It is relocated to
`rana_qgis_plugin/utils/api_logging.py`, alongside `utils/api.py` and
`utils/settings.py`. The corresponding test file moves from
`tests/test_threedi_api_logging.py` to `tests/test_utils_api_logging.py`.

**Integration points for REST logging** (unchanged from Tasks 1-3): of the
three API client factory functions in `simulation/threedi_calls.py`, only
`get_api_client_with_personal_api_token` is actually called anywhere in the
plugin. The logger is installed inside that factory immediately after
constructing the client. The other two factories are unused in the plugin and
remain uninstrumented.

**Integration points for upload logging** (new in this extension):

- `rana_qgis_plugin/workers/upload.py:177` — `requests.put(upload_url, data=file)`
  (Rana project-file upload)
- `rana_qgis_plugin/simulation/utils.py:282` — `requests.put(upload.put_url, data=file)`
  (ThreeDi file upload, e.g. boundary conditions, initial waterlevels, laterals)
- `rana_qgis_plugin/simulation/workers.py:1299` and `:1340` —
  `threedi_api_client.files.upload_file(upload.put_url, ...)` (schematisation
  SQLite/GeoPackage and raster uploads)

## User Scenarios & Testing

### User Story 1 - Developer sees ThreeDi request attempts (Priority: P1) — implemented

A developer or support engineer investigating a reported problem (e.g. "the
simulation list doesn't load") wants to see which ThreeDi API requests the
plugin attempted, including ones that failed before getting a response.

**Why this priority**: This is the entire purpose of the feature — without it,
there's no way to confirm whether a ThreeDi API call was even attempted.

**Independent Test**: Enable `Rana/log_api_requests`, trigger a ThreeDi API
action (e.g. open the simulation overview), and confirm a log line appears in
the QGIS Log Messages panel under the "Rana" category showing the HTTP method
and URL.

**Acceptance Scenarios**:

1. **Given** the setting is enabled, **When** any `ThreediCalls` method
   triggers an HTTP request, **Then** a log line is written to the Rana log
   category showing the method, path, and (redacted) query params, before the
   network call is made.
2. **Given** the setting is enabled and a request raises an exception during
   the transport call (e.g. connection error), **Then** a log line is written
   at Warning level indicating the request failed, referencing the same
   request summary.

---

### User Story 2 - Logging is opt-in and discoverable (Priority: P1) — implemented, setting renamed in this extension

A regular user who never touches QgsSettings should see no behavior change.
A developer who wants to check whether logging is active should be able to
see the setting's value (if set) in the Advanced Settings section of the
settings dialog.

**Why this priority**: This is a debugging aid, not a user-facing feature. It
must be inert by default, but discoverable for developers via the existing
Advanced Settings display.

**Independent Test**: With the setting unset (default), use the plugin
normally and confirm the Rana log category shows no extra request-attempt
lines. Set `Rana/log_api_requests=true` via QgsSettings/QGIS.ini and confirm
logging resumes, and the value is listed in the settings dialog's Advanced
Settings section.

**Acceptance Scenarios**:

1. **Given** the setting is not set, **When** the plugin constructs a
   ThreeDi API client or performs a covered upload, **Then** no logger is
   installed and behavior is unchanged from before this feature.
2. **Given** the setting is enabled, **When** ThreeDi API calls or covered
   uploads are made, **Then** behavior matches User Stories 1 and 3.
3. **Given** the setting has a value, **When** the settings dialog is opened,
   **Then** `log_api_requests` appears in the read-only Advanced Settings
   section.

---

### User Story 3 - Developer sees file upload attempts (Priority: P1) — new in this extension

A developer investigating a failed or stuck file upload (Rana project file,
or a ThreeDi schematisation/raster/boundary-condition upload) wants to confirm
the upload was actually handed to its HTTP transport, even if the transfer
ultimately fails. Today, neither the ThreeDi REST logger nor QGIS's network
debugger covers these transfers, since they bypass both `NetworkManager` and
the ThreeDi REST client.

**Why this priority**: Upload failures are a common support scenario, and the
existing ThreeDi API logger only shows the API call that creates the upload
record and returns a presigned URL — not whether the subsequent file transfer
was attempted.

**Independent Test**: Enable `Rana/log_api_requests`, perform a Rana project
file upload and a ThreeDi schematisation SQLite upload, and confirm each
produces a log line showing the PUT method and host/path (no query string),
before the actual transfer begins.

**Acceptance Scenarios**:

1. **Given** the setting is enabled, **When** a file is uploaded via
   `requests.put()` at `workers/upload.py:177` or `simulation/utils.py:282`,
   **Then** an Info-level log line is written showing `PUT` and the host/path
   (no query string) before the request is sent.
2. **Given** the setting is enabled, **When** a file is uploaded via
   `threedi_api_client.files.upload_file()` at `simulation/workers.py:1299`
   or `:1340`, **Then** the same kind of log line is written before the
   transfer begins, via a logging-enabled `urllib3.PoolManager` passed as the
   `pool` argument.
3. **Given** the setting is enabled and an upload attempt raises (e.g.
   network error, non-2xx response), **Then** a Warning-level log line is
   written referencing the same summary and exception type, and the original
   exception propagates unchanged.
4. **Given** the setting is not set, **When** any of the above uploads occur,
   **Then** no additional log lines are produced and upload behavior
   (retries, callbacks, timeouts) is unchanged.

---

### Edge Cases

- What happens if the installed `threedi-api-client` version doesn't expose
  `_client.rest_client.request` (internal structure changed)? The REST
  wrapper installation must fail safely (log a one-time warning, or silently
  skip) and must never prevent the API client from being usable.
- What happens if request-summary formatting or QGIS log emission itself
  raises? Logging must fail open: diagnostic failures must not prevent the
  original transport method (REST or upload) from being called, or change its
  result/error.
- What happens for multipart/file upload requests? They are logged the same
  way (method + host/path only); request/response bodies and file contents
  are never logged.
- What happens during pagination (`paginated_fetch`)? Each page is a separate
  transport call and is logged separately — this is expected and useful for
  diagnosing pagination issues.
- What happens to auth/token-refresh requests made internally by the ThreeDi
  client? These are logged too, since the wrapper sits at the transport level
  below any internal call distinctions.
- What happens to query strings on upload URLs? They are **never logged**,
  not even redacted — presigned upload URLs can embed signatures/credentials
  in the query string itself, so omitting the entire query string is safer
  than attempting to redact specific parameter names.
- What happens to the `upload_file()` retry/backoff behavior when a logging
  pool is injected? The injected `urllib3.PoolManager` must be constructed
  with the same retry policy `upload_file()` would otherwise use by default
  (`Retry(3, backoff_factor=1.0)`, matching `threedi_api_client.files.get_pool()`),
  so upload resilience is unchanged.

## Requirements

### Functional Requirements

**Phase 1 (implemented): ThreeDi REST API request logging**

- **FR-001**: The plugin MUST provide a reusable transport-logging wrapper
  (`install_request_logger`) in `rana_qgis_plugin/utils/api_logging.py`
  (relocated from `simulation/threedi_api_logging.py` in this extension).
- **FR-002**: `get_api_client_with_personal_api_token()` in
  `simulation/threedi_calls.py` MUST call `install_request_logger(api_client)`
  when `Rana/log_api_requests` is enabled, immediately after constructing the
  client and before returning it.
- **FR-003**: The wrapper MUST log a summary (HTTP method, host+path, and
  redacted query params) at `Qgis.MessageLevel.Info` immediately before
  invoking the original transport method.
- **FR-004**: If the wrapped transport call raises an exception, the wrapper
  MUST log a second line at `Qgis.MessageLevel.Warning` referencing the same
  request and exception type (including `ApiException.status` when
  available), without raw exception text, reason, headers, or response body,
  then re-raise the original exception unchanged.
- **FR-005**: The wrapper MUST NOT log request or response bodies, and MUST
  NOT log headers.
- **FR-006**: The wrapper MUST redact values for known sensitive query
  parameter names (containing `token`, `password`, `key`, `secret`, or
  `authorization`, case-insensitive), in both the query-params argument and
  any query string embedded in the URL.
- **FR-007**: Log lines MUST use the "Rana" QGIS log category (via
  `QgsMessageLog.logMessage(msg, PLUGIN_NAME, level)`).
- **FR-008**: If the wrapper cannot be installed (e.g. unexpected client
  internals), the plugin MUST continue to function normally with no wrapper
  installed; this MUST NOT raise or block plugin usage.
- **FR-009**: Failures while constructing or emitting diagnostic log messages
  MUST NOT prevent the original transport method from being called, change
  its return value, or replace an exception it raises.

**Phase 2 (this extension): rename the setting, add upload-attempt logging**

- **FR-010**: The plugin MUST rename the setting from
  `Rana/log_threedi_api_requests` to `Rana/log_api_requests` (default
  `False`), with accessor `get_log_api_requests()` replacing
  `get_log_threedi_api_requests()` in `utils/settings.py`. No compatibility
  alias is required; the old key was never part of a release.
- **FR-011**: `get_api_client_with_personal_api_token()` MUST continue to
  call `install_request_logger(...)` only when `get_log_api_requests()` is
  true.
- **FR-012**: The setting MUST appear in `get_advanced_settings()` (key
  `log_api_requests`) so its value is shown in the read-only Advanced
  Settings section of the settings dialog when set.
- **FR-013**: The plugin MUST provide an upload-logging helper that, when
  `get_log_api_requests()` is true, wraps `requests.put()` calls at
  `workers/upload.py:177` and `simulation/utils.py:282` to log an Info-level
  summary (method + host/path, no query string) before the request is sent,
  and a Warning-level summary (with exception type) if the call raises,
  without altering the call's arguments, return value, or raised exception.
- **FR-014**: The plugin MUST provide a logging-enabled `urllib3.PoolManager`
  factory that, when `get_log_api_requests()` is true, is passed as the
  `pool` argument to `threedi_api_client.files.upload_file()` calls at
  `simulation/workers.py:1299` and `:1340`. The pool MUST log the same kind
  of Info/Warning summary around each request it handles, and MUST be
  constructed with the same retry policy `upload_file()` uses by default
  (`Retry(3, backoff_factor=1.0)`), so upload retry behavior is unchanged.
- **FR-015**: Upload log summaries MUST NOT include the query string of the
  upload URL under any circumstances (not even redacted), MUST NOT include
  headers, and MUST NOT include file contents.
- **FR-016**: When `Rana/log_api_requests` is not set or `False`, no upload
  logger/pool is installed, and upload behavior (including retries, timeouts,
  and progress callbacks) is unchanged from before this feature.
- **FR-017**: Diagnostic logging for uploads MUST fail open: failures while
  building the summary or emitting the log message MUST NOT prevent the
  upload call from proceeding or change its result/exception.

### Key Entities

- **Request summary**: An internal, ephemeral string built per call — for
  REST requests: HTTP method, URL path, and redacted query params. For
  uploads: HTTP method and host/path only, with the query string always
  omitted. Not persisted; exists only as a log line.

## Success Criteria

### Measurable Outcomes

- **SC-001**: When `Rana/log_api_requests` is enabled, every HTTP request
  made through a client returned by `get_api_client_with_personal_api_token()`
  produces a corresponding log line in the Rana category, including calls
  that fail before receiving a response.
- **SC-002**: When `Rana/log_api_requests` is disabled or unset, there is no
  observable difference in behavior, logs, or performance compared to before
  this feature existed, for both REST calls and uploads.
- **SC-003**: No request or upload logged under this feature ever contains a
  raw value for a query parameter whose name contains a sensitive term
  (REST), and no upload log ever contains any part of the upload URL's query
  string.
- **SC-004**: When `Rana/log_api_requests` is enabled, performing a Rana
  project-file upload, a ThreeDi `requests.put()` upload, and a ThreeDi
  schematisation/raster upload via `upload_file()` each produce a
  corresponding Info-level log line before the transfer begins.
- **SC-005**: Upload retry count, backoff timing, and progress-callback
  behavior are identical with logging enabled or disabled.

## Out of Scope

- Making ThreeDi API calls visible in QGIS's native network-manager debugging
  tools (would require bridging two transport stacks — see prior research).
- Logging response bodies or detailed timing/retry internals of `urllib3`.
- A user-facing *writable* UI toggle for this setting (it remains
  QgsSettings/QGIS.ini-configured, shown read-only in Advanced Settings).
- Retry/resilience changes to the ThreeDi API client or to uploads beyond
  preserving existing behavior.
- Instrumenting `get_api_client()` and `get_api_client_with_tokens()` in
  `simulation/threedi_calls.py` — unused anywhere in the plugin.
- Logging the DWF-labeling upload/download in `processing/label_dwf.py`.
- Logging any file **download** path (Rana or ThreeDi).
</content>
