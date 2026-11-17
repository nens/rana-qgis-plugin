---
feature: feat_492_proper_model_status
status: planned
created: 2026-11-17
decisions: [20261117-1000-model-generating-state]
---

# Proper model status (is_generating) Design

## Overview
`SchematisationRevisionHistoryDialog` uses the 3Di `is_generating` filter on
`GET /v3/threedimodels/` to block Create and Delete of a Rana model on a revision
whose model is being generated.

## User Stories
- As a user, I cannot create or delete a model for a revision while its model is
  generating, and I see why.
- As a user, I cannot exceed the model limit by creating models while others generate.

## Components
### ThreediCalls (`simulation/threedi_calls.py`)
New `fetch_generating_models(schematisation_id)` calling
`threedimodels_list(is_generating=True, revision__schematisation__id=...)`
(paginated), returning the models; the dialog only needs their `revision_id`s.

### SchematisationRevisionHistoryDialog.fetch_page (`widgets/version_history_dialog.py`)
- Compute `generating_ids` and `model_ids` (from `has_threedimodel`).
- `model_count = len(model_ids | generating_ids)`.
- Per row metadata: `is_generating`; when true, `model_enabled=False` and tooltip
  "The Rana model for this revision is being generated. Click Refresh to update."
- Label stays "Create"/"Delete" (generating revision without model -> "Create", disabled).

### Click-time guard
`ThreediCalls.is_revision_generating(revision_id)` runs before `create_model` and
`delete_model` acts (before the delete confirmation). If true: message, block row, abort.
Protects against stale state with manual refresh. Fails closed: if the check errors, show
the error and abort. A failing load-time `fetch_generating_models` goes through the existing
fetch error path (`show_fetch_error`).

### Post-action updates
`create_model` already disables the button; set the same generating tooltip and
metadata. `update_action_columns_after_delete_success` keeps its limit logic; it must
not re-enable rows with `is_generating`.

## Scope
Per revision only; manual Refresh; no polling. Not covered: other dialogs, simulation
button state, Processes panel changes.

## Open Questions
- Whether `has_threedimodel` is already true for a generating model (affects nothing
  due to the set union).
- Confirm `ThreediModel.revision_id` is populated on list results (present in schema).

## Manual testing
Rana file history -> revision history dialog: create a model, Refresh while it
generates (button disabled, tooltip), Refresh after (Delete enabled); at the limit
with one generating model, other Create buttons stay disabled.
