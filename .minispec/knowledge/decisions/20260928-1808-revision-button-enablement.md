---
type: decision
id: 20260928-1808-revision-button-enablement
date: 2026-09-28
status: accepted
supersedes: 20260928-1804-synchronous-revision-batches
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/simulation/threedi_calls.py
tags: [file-history, schematisation, actions, pagination]
participants: [engineer, implementation-agent]
---

# Fetch All Revisions for Exact Legacy Action Enablement

## Context

Revision rows include `Simulation` and `Rana Model` buttons. Their enabled
state should preserve the legacy behavior. In particular, a `Create` model
button depends on the total number of revisions that already have a model,
compared with the schematisation's `threedimodel_limit`.

The new dialog could fetch revisions in batches, but a first-page-only count
would not know about models on later pages. The existing
`fetch_schematisation_revisions()` method already fetches the complete list.

## Options Considered

### Option 1: Fetch all revisions synchronously

Use the existing all-pages method, count model-bearing revisions across the
complete result, and then render all rows with exact button state.

- ✅ Matches legacy behavior.
- ✅ Correct button state is available immediately.
- ✅ Does not require a new aggregate API.
- ❌ Can make multiple synchronous requests and temporarily block QGIS.

### Option 2: Fetch bounded pages and count only loaded rows

Render the first page and update model-button state as more pages load.

- ✅ Limits initial requests.
- ❌ Initial button state may be incorrect.
- ❌ Does not preserve the legacy model-limit rule.

### Option 3: Add/use an aggregate model-count endpoint

Fetch pages incrementally and separately retrieve the total model count.

- ✅ Could preserve exact state and bounded page loading.
- ❌ No suitable aggregate endpoint has been established.
- ❌ Adds a separate API dependency and is deferred.

## Decision

We chose **Option 1: Fetch all revisions synchronously** for the initial
implementation.

The dialog will call `fetch_schematisation_revisions()`, count
`revision.has_threedimodel` across the full result, and compare that count with
`schematisation["schematisation"]["threedimodel_limit"]`.

Button behavior is ported from the legacy view:

- `Simulation` is `New`, enabled only when the revision has a model; otherwise
  it is disabled with the model-required tooltip.
- `Rana Model` is `Delete`, enabled, when the revision has a model.
- `Rana Model` is `Create`, enabled, when the revision has no model and the
  global model limit has not been reached.
- `Create` is disabled with the legacy model-limit tooltip when the limit has
  been reached.
- The `Simulation` button opens a placeholder dialog and does not invoke a
  simulation. The `Rana Model` buttons use the concrete Create/Delete behavior
  defined by `20260930-1132-rana-model-history-actions`.

The existing all-pages method's behavior and callers must remain compatible.
If complete loading proves too slow, a future change may introduce a
`QgsTask`, an aggregate count endpoint, or both.

## Consequences

### Positive

- ✅ Exact legacy enablement is preserved.
- ✅ Placeholder actions have correct availability from the first display.
- ✅ No speculative API change is required.

### Negative

- ⚠️ Large histories may make the synchronous initial load slow.
- ⚠️ A later asynchronous implementation must preserve the complete-count
  semantics.

## Code References

- Legacy enablement: `rana_qgis_plugin/legacy/widgets/revisions_view.py:187-229`
- Existing all-pages wrapper:
  `rana_qgis_plugin/simulation/threedi_calls.py:1249-1259`
- Existing model-limit field:
  `rana_qgis_plugin/legacy/widgets/revisions_view.py:193`

## Related Decisions

- `20260928-1804-synchronous-revision-batches` (superseded)
- `20260928-1752-revision-action-stubs`
- `20260930-1132-rana-model-history-actions`
