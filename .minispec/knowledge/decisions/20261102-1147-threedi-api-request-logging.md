---
type: decision
id: 20261102-1147-threedi-api-request-logging
date: 2026-11-02
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/simulation/threedi_api_logging.py
  - rana_qgis_plugin/simulation/threedi_calls.py
  - rana_qgis_plugin/utils/settings.py
tags: [debugging, logging, threedi-api-client, network]
participants: [engineer, implementation-agent]
---

# Log ThreeDi API request attempts via a transport-level wrapper

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
package. Logging is initially unconditional during development so its volume
and usefulness can be evaluated; the intended final behavior is opt-in via a
hidden setting added only after the stabilization period.

In the inspected version of `threedi_api_client` (5.0.5), the synchronous
request path is:

```
ThreediApi._client.rest_client.request(method, url, query_params=..., ...)
  -> urllib3.PoolManager.request(...)
```

`RESTClientObject.request(...)` is the last point in the client before control
passes to `urllib3`. Logging immediately before this call is made captures
intent-to-send, independent of whether the network call ultimately succeeds.

## Options Considered

### Option 1: Log at the `ThreediCalls` method level (e.g. decorate `fetch_simulations`, etc.)

- Simple, no dependency on client internals
- Doesn't capture pagination sub-calls or internal auth/token-refresh requests
  distinctly from the "main" call
- Doesn't reliably show HTTP method/URL — that information isn't available at
  this layer without re-deriving it
- Wouldn't catch requests that fail before entering a `ThreediCalls` method
  wrapper in some edge cases (e.g. errors raised during client construction)

### Option 2: Wrap the transport (`RESTClientObject.request`) via monkey-patching on each constructed client instance

- Captures the actual HTTP method, URL, and query params for every request
  the client sends, including pagination and internal auth calls
- Captures requests that fail before a response (logs before calling through)
- Touches client internals (`_client.rest_client`), so it must be defensive
  and versioned against the installed `threedi-api-client`
- Fully contained in plugin code — no changes to the `threedi-api-client`
  package

### Option 3: Subclass `RESTClientObject` and inject it via client configuration

- Would be a "cleaner" OOP approach if the client supported pluggable REST
  client classes
- Not confirmed to be supported by `threedi-api-client`'s configuration
  surface; would require more invasive attribute manipulation than Option 2
  for equivalent behavior
- No clear advantage over Option 2 given the uncertainty

## Decision

We chose **Option 2: monkey-patch the transport request method on the
client instance, installed by the plugin's personal-token client factory.**

Specifically:

- During development, the logger is installed unconditionally in
  `simulation/threedi_calls.py:get_api_client_with_personal_api_token()`
  immediately after client construction. The final
  task, after stabilization, adds the hidden setting
  `Rana/log_threedi_api_requests` (boolean, default `False`) and makes
  installation conditional on it. It follows the existing
  `use_plugin_excepthook` pattern and is not exposed in the advanced settings
  dialog.
- Only `get_api_client_with_personal_api_token()` is wired because the other
  two factories in `simulation/threedi_calls.py` (`get_api_client` and
  `get_api_client_with_tokens`) are unused in the plugin.
- The wrapper logs an `Info`-level message to the QGIS "Rana" log category
  (via the same mechanism as `UICommunication.log_msg`) with the HTTP method,
  host+path, and redacted query params, immediately before calling through to
  the original transport method.
- If the wrapped call raises, the wrapper logs a `Warning`-level message
  referencing the same request summary and the exception type; include
  `ApiException.status` when available. It never logs raw exception text,
  reason, headers, or response body, because the client's exception string
  can contain those values. The original exception is re-raised unchanged.
- Sensitive query parameter names containing `token`, `password`, `key`,
  `secret`, or `authorization` (case-insensitive) have their values redacted
  as `***`. Redaction applies to both the separately supplied query params and
  query values embedded in the URL. Headers and bodies are never logged.
- All requests the transport sends are logged, including internal
  auth/token-refresh requests — we do not attempt to filter to only
  "application-level" calls, since that distinction isn't reliably available
  at the transport layer and the broader visibility is more useful for
  debugging auth issues.
- If the wrapper cannot be installed (e.g. the client's internal structure
  doesn't match expectations), this must fail safely: log a warning once and
  continue without the wrapper, never blocking plugin usage.
- Diagnostic logging must fail open: if summary construction or QGIS log
  emission raises, the original transport request is still called. If the
  transport raises, a failed warning-log attempt must not replace the original
  transport exception.
- The inspected transport receives query params as a sequence of `(name,
  value)` pairs; the helper is typed for that actual representation and does
  not add unused mapping support.

## Consequences

### Positive

- ✅ During development, request attempts are logged without requiring setup;
  after stabilization, users can opt in via a hidden setting.
- ✅ No changes to the `threedi-api-client` package.
- ✅ After stabilization and addition of the setting, logging is disabled by
  default for users who have not explicitly enabled it.
- ✅ Any caller of `get_api_client_with_personal_api_token()` receives a
  wrapped client; requests include pagination without instrumenting each API
  method individually.

### Negative

- ⚠️ Relies on internal attributes of the installed `threedi-api-client`
  version (`_client.rest_client.request`); a future client upgrade could
  silently stop logging if the internal structure changes. Mitigated by
  FR-008 (fail safely, never block usage).
- ⚠️ Does not confirm requests were actually transmitted/received by the
  server — only that they were handed to the transport. This is a known and
  accepted limitation, not a correctness gap for this feature's purpose.
- ⚠️ Does not surface individual `urllib3` retry attempts, only the logical
  request as seen by the client.

### Neutral

- During development/stabilization logging is unconditional; this is temporary
  and is followed by the opt-in setting as the final task.
- This is a developer/support-facing diagnostic feature; the setting
  intentionally has no discoverability for regular end users.
- Bridging ThreeDi calls into QGIS's native network debugging tools remains
  out of scope and would be a separate, much larger effort if ever pursued.

## Code References

- Client construction/integration point:
  `rana_qgis_plugin/simulation/threedi_calls.py:get_api_client_with_personal_api_token()`
- Settings pattern to follow: `rana_qgis_plugin/utils/settings.py:138-141`
  (`get_use_plugin_excepthook`)
- Logging mechanism to reuse: `rana_qgis_plugin/communication.py:120-134`
  (`UICommunication.log_msg` / `QgsMessageLog.logMessage`)
- Transport hook point (installed version 5.0.5):
  `threedi_api_client.openapi.rest.RESTClientObject.request`, reached via
  `ThreediApi._client.rest_client.request`

## Related Decisions

None yet — this is the first decision record for this feature.

## Notes

Manual testing should cover: during development, triggering a normal ThreeDi
API action (e.g. opening the simulation overview) to confirm log lines appear;
after the setting is added, confirming the default-off and explicitly enabled
behavior; and, if feasible, simulating a network failure (e.g. invalid host) to
confirm the Warning-level failure log appears.
