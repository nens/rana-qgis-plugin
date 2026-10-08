---
type: decision
id: 20260928-1804-synchronous-revision-batches
date: 2026-09-28
status: superseded
supersedes: null
superseded_by: 20260928-1808-revision-button-enablement
impacts:
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/simulation/threedi_calls.py
tags: [file-history, schematisation, pagination, performance]
participants: [engineer, implementation-agent]
---

# Start with Complete Revision Loading for Exact Button State

## Context

Schematisation revision retrieval supports bounded requests through
`fetch_schematisation_revisions_with_count(limit, offset)`. However, the
revision action buttons need the exact total number of revisions that already
have a Rana model in order to enforce `threedimodel_limit`, matching the
legacy `RevisionsView` behavior.

The history dialog also needs the revision action buttons to have correct state
as soon as the window opens. Counting only loaded pages would make the Create
button state incorrect until older pages happened to be loaded.

## Options Considered

### Option 1: Fetch all revisions synchronously

Use the existing `fetch_schematisation_revisions()` all-pages method on open,
then calculate the model count and render all rows with the legacy button
enablement rules.

- ✅ Preserves exact legacy enablement behavior.
- ✅ Gives the user correct button state immediately.
- ✅ Avoids a new aggregate API dependency.
- ❌ May issue multiple synchronous requests for a large revision history.
- ❌ Can block QGIS longer than a single bounded request.

### Option 2: Synchronous bounded batches

Fetch one page and calculate button state only from loaded revisions.

- ✅ Bounded initial work.
- ❌ Button state can be wrong while older revisions are not loaded.
- ❌ Does not preserve legacy model-limit semantics.

### Option 3: Add an aggregate model-count API

Fetch revisions in batches and separately request the number of models.

- ✅ Could preserve exact button state and bounded revision loading.
- ❌ No suitable aggregate endpoint has been established yet.
- ❌ Adds an API dependency and is deferred.

## Decision

We chose **Option 1: Fetch all revisions synchronously**.

The new dialog will use `fetch_schematisation_revisions()`, count
`has_threedimodel` across the complete result, and render the legacy button
enablement state. The method's existing all-pages contract remains unchanged
for its other callers.

The initial implementation remains synchronous. If complete revision loading
proves too slow, a later change may introduce an aggregate count endpoint, a
`QgsTask`, or both.

## Consequences

### Positive

- ✅ Initial button state is exact and straightforward to test.
- ✅ Existing non-history callers retain their behavior.
- ✅ The implementation matches the legacy model-limit behavior.

### Negative

- ⚠️ A large revision history can briefly block QGIS.
- ⚠️ A future async conversion will need to preserve model-count and button
  state behavior.

## Code References

- All-pages method: `rana_qgis_plugin/simulation/threedi_calls.py:1249`
- One-page alternative: `rana_qgis_plugin/simulation/threedi_calls.py:1261`
- Current callers of all-pages method:
  `rana_qgis_plugin/simulation/utils.py:684`
- Current upload caller:
  `rana_qgis_plugin/simulation/upload_wizard/upload_wizard.py:877`
