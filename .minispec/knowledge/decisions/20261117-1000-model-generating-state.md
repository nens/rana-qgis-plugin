# Decision: Block Rana model Create/Delete per revision while generating

**Date**: 2026-11-17 10:00
**Status**: Accepted (in progress)
**Feature**: `feat_492_proper_model_status`

## Context

The "Rana Model" column in `SchematisationRevisionHistoryDialog` derives its
state from `revision.has_threedimodel` and local updates after create/delete.
A model that is still being generated can show an enabled "Create" button.
`is_generating` is a query filter on `GET /v3/threedimodels/`, not a model field.

## Decision

- Query `threedimodels_list(is_generating=True, revision__schematisation__id=...)`
  and map results to revision ids.
- Scope: only the affected revision's Create/Delete button is blocked.
- Presentation: button disabled, label unchanged (Create/Delete), tooltip explains
  the model is being generated and to click Refresh. Matches the existing
  `create_model` disabled+tooltip pattern.
- Freshness: manual Refresh only; no polling.

## Consequences

- No new label state; only metadata + tooltip logic changes.
- Extra API call per dialog load.

## Addendum: limit counting

Revisions with a generating model count toward `threedimodel_limit`. The count is
the size of the union of revision ids having a model (`has_threedimodel`) and
revision ids with a generating model, so nothing is double-counted.

## Addendum: click-time guard

Manual refresh means dialog state can be stale. On Create/Delete click, the plugin
checks `threedimodels_list(revision__id=X, is_generating=True, limit=1)`; if generating,
it shows a message, blocks the row and aborts. The load-time call is still needed for
visible state and limit counting (one request instead of N per-revision requests).

## Addendum: failure handling

Both the load-time and click-time checks fail closed: on error, show it and do not offer or perform Create/Delete.
