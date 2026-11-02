# Feature Specification: ThreeDi API Request Logging

**Created**: 2026-11-02
**Status**: Planned
**Branch**: feat_5343_api_logging
**Input**: Developer need to see ThreeDi API (threedi-api-client) HTTP request
attempts in QGIS's debugging/logging tools, matching the visibility that
`NetworkManager`-based Rana API calls already have.

## Background

Rana API calls made via `NetworkManager` (Qt Network / `QgsNetworkAccessManager`)
are visible through QGIS's network debugging tools. ThreeDi API calls made via
the external `threedi-api-client` package are not, because that package uses
its own `urllib3`-based transport, entirely separate from QGIS's network stack.

This feature does not attempt to route ThreeDi API calls through QGIS's
network manager (a large transport-bridging effort, out of scope). Instead, it
adds a developer-facing log of HTTP request attempts made by the ThreeDi API
client, written to QGIS's existing Log Messages panel under the "Rana"
category.

**Rollout sequencing**: during development, logging is initially installed
unconditionally (no setting yet) so the engineer can evaluate it under normal
plugin use. After that stabilization period, the final task adds a hidden
`Rana/log_threedi_api_requests` setting (default `False`), making the intended
final behavior opt-in. This is a deliberate development sequence; default-on
is not the intended shipped behavior. See `tasks.md` for the task sequencing.

**Integration point**: of the three API client factory functions in
`simulation/threedi_calls.py`, only `get_api_client_with_personal_api_token`
is actually called anywhere in the plugin, via `get_threedi_api()` in
`utils/generic.py`. The logger is installed inside that factory immediately
after constructing the client, so any caller of this factory receives the
wrapped client. The other two (`get_api_client`, `get_api_client_with_tokens`)
are currently unused in the plugin and are left uninstrumented; this is
explicitly out of scope (see below).

## User Scenarios & Testing

### User Story 1 - Developer sees ThreeDi request attempts during the stabilization phase (Priority: P1)

A developer or support engineer investigating a reported problem (e.g. "the
simulation list doesn't load") wants to see which ThreeDi API requests the
plugin attempted, including ones that failed before getting a response. During
initial rollout this is always on (no setting exists yet) so the behavior can
be exercised and validated under normal, everyday plugin use before being
gated behind a setting.

**Why this priority**: This is the entire purpose of the feature — without it,
there's no way to confirm whether a ThreeDi API call was even attempted.

**Independent Test**: Trigger a ThreeDi API action (e.g. open the simulation
overview) and confirm a log line appears in the QGIS Log Messages panel under
the "Rana" category showing the HTTP method and URL.

**Acceptance Scenarios**:

1. **Given** the logging wrapper is installed (default-on, pre-setting phase),
   **When** any `ThreediCalls` method triggers an HTTP request, **Then** a log
   line is written to the Rana log category showing the method, path, and
   (redacted) query params, before the network call is made.
2. **Given** the logging wrapper is installed and a request raises an
   exception during the transport call (e.g. connection error), **Then** a
   log line is written at Warning level indicating the request failed,
   referencing the same request summary.

---

### User Story 2 - Logging becomes opt-in once stabilized (Priority: P1)

Once the engineer is satisfied the logging behaves well (useful, not noisy,
no leaked secrets), a hidden setting is added so the default behavior for all
other users reverts to no extra log noise.

**Why this priority**: This is a debugging aid, not a user-facing feature.
Once validated, it must be inert by default so it doesn't affect regular
users or environments where it wasn't deliberately enabled.

**Independent Test**: With the setting unset (default, post-setting phase),
use the plugin normally and confirm the Rana log category shows no extra
request-attempt lines. With the setting enabled, confirm the same log lines
from User Story 1 reappear.

**Acceptance Scenarios**:

1. **Given** the hidden setting has been added and is not set, **When** the
   plugin constructs a ThreeDi API client, **Then** no wrapper is installed
   and the client behaves exactly as it did before this feature.
2. **Given** the hidden setting is enabled, **When** ThreeDi API calls are
   made, **Then** behavior matches User Story 1.

---

### Edge Cases

- What happens if the installed `threedi-api-client` version doesn't expose
  `_client.rest_client.request` (internal structure changed)? The wrapper
  installation must fail safely (log a one-time warning, or silently skip) and
  must never prevent the API client from being usable.
- What happens if request-summary formatting or QGIS log emission itself
  raises? Logging must fail open: diagnostic failures must not prevent the
  original transport method from being called or replace its result/error.
- What happens for multipart/file upload requests? They are logged the same
  way (method + path); large bodies are never logged.
- What happens during pagination (`paginated_fetch`)? Each page is a separate
  transport call and is logged separately — this is expected and useful for
  diagnosing pagination issues.
- What happens to auth/token-refresh requests made internally by the client?
  These are logged too, since the wrapper sits at the transport level below
  any internal call distinctions (see Decision: log everything the transport
  sends).

## Requirements

### Functional Requirements

**Phase 1 (initial implementation, default-on, no setting):**

- **FR-001**: The plugin MUST provide a reusable transport-logging wrapper
  (`install_request_logger`) in a new module,
  `rana_qgis_plugin/simulation/threedi_api_logging.py`.
- **FR-002**: `get_api_client_with_personal_api_token()` in
  `simulation/threedi_calls.py` MUST call
  `install_request_logger(api_client)` unconditionally immediately after
  constructing the client and before returning it.
- **FR-003**: The wrapper MUST log a summary (HTTP method, host+path, and
  redacted query params) at `Qgis.MessageLevel.Info` immediately before
  invoking the original transport method, i.e. before the request may or may
  not actually be sent over the network. The summary helper MUST support the
  query parameter representation received from the installed client, which
  may be a sequence of `(name, value)` pairs rather than a mapping.
- **FR-004**: If the wrapped transport call raises an exception, the wrapper
  MUST log a second line at `Qgis.MessageLevel.Warning` referencing the same
  request and exception type. For `ApiException`, it MAY include the HTTP
  status when available. It MUST NOT log the raw exception text, reason,
  headers, or response body. The wrapper then re-raises the original exception
  unchanged.
- **FR-005**: The wrapper MUST NOT log request or response bodies, and MUST
  NOT log headers.
- **FR-006**: The wrapper MUST redact values for known sensitive query
  parameter names (e.g. names containing `token`, `password`, `key`, `secret`,
  or `authorization`, case-insensitive) by replacing the value with `***`.
  Redaction MUST be applied to both the query-params argument and any query
  string embedded in the URL before the request summary is logged.
- **FR-007**: Log lines MUST use the "Rana" QGIS log category (via
  `QgsMessageLog.logMessage(msg, PLUGIN_NAME, level)`), consistent with how
  `communication.py`'s `UICommunication.log_msg` logs.
- **FR-008**: If the wrapper cannot be installed (e.g. unexpected client
  internals), the plugin MUST continue to function normally with no wrapper
  installed; this MUST NOT raise or block plugin usage.
- **FR-009**: Failures while constructing or emitting diagnostic log messages
  MUST NOT prevent the original transport method from being called, change its
  return value, or replace an exception it raises.

**Phase 2 (final task, after stabilization — adds the hidden setting):**

- **FR-010**: The plugin MUST provide a hidden QgsSettings boolean,
  `Rana/log_threedi_api_requests` (default `False`), following the pattern of
  `get_use_plugin_excepthook()` in `utils/settings.py`.
- **FR-011**: `get_api_client_with_personal_api_token()` MUST only call
  `install_request_logger(...)` when this setting is enabled; FR-002's
  unconditional call is replaced by a conditional one.
- **FR-012**: The setting MUST NOT appear in `get_advanced_settings()` / the
  advanced settings dialog; it is QgsSettings-only, undocumented in the UI.

### Key Entities

- **Request summary**: An internal, ephemeral string built per call —
  HTTP method, URL path, and redacted query params. Not persisted; exists
  only as a log line.

## Success Criteria

### Measurable Outcomes

- **SC-001**: During Phase 1 (development, unconditional), every HTTP request
  made through a client returned by `get_api_client_with_personal_api_token()` produces a
  corresponding log line in the Rana category, including calls that fail
  before receiving a response.
- **SC-002**: During Phase 2 (setting added, default `False`), with the
  setting disabled, there is no observable difference in behavior, logs, or
  performance compared to before this feature existed.
- **SC-003**: No request logged under this feature ever contains a raw
  value for a query parameter whose name contains a sensitive term, whether
  supplied separately or embedded in the URL.

## Out of Scope

- Making ThreeDi API calls visible in QGIS's native network-manager debugging
  tools (would require bridging two transport stacks — see prior research).
- Logging response bodies or detailed timing/retry internals of `urllib3`.
- A user-facing UI/settings-dialog toggle for this setting.
- Retry/resilience changes to the ThreeDi API client.
- Instrumenting `get_api_client()` and `get_api_client_with_tokens()` in
  `simulation/threedi_calls.py` — these are currently unused anywhere in the
  plugin, so they are left uninstrumented.
