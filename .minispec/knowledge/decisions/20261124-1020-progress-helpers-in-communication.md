---
type: decision
id: 20261124-1020-progress-helpers-in-communication
date: 2026-11-24
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/communication.py
  - rana_qgis_plugin/widgets/schematisation_new_wizard.py
  - rana_qgis_plugin/loader.py
tags: [message-bar, progress, refactor]
participants: [margriet, agent]
---

# Progress-item helpers live in communication.py

## Context

`20261116-1200-schematisation-step-progress` intended the step-progress helpers
to be plain functions in `communication.py`. They ended up as static methods on
`SchematisationWizardBase`. The revision upload now needs a plain
"set value + label" update and the same "remove this item" call, which has
nothing to do with the wizard.

## Options Considered

- Add `update_progress` to `SchematisationWizardBase`: smallest diff, but the
  revision upload would depend on a wizard class for message-bar helpers.
- **Move the helpers to `communication.py`** (chosen), next to `progress_bar()`.

## Decision

Module-level functions in `rana_qgis_plugin/communication.py`:

- `update_progress(pb, value, detail=None)`: sets the value and, if given, the
  message text. Ignores `None` and dismissed bars (logs instead).
- `update_step_progress(pb, step, step_pct, detail=None)`: three-step mapping,
  delegates to `update_progress`.
- `finish_progress(iface, pb)`: removes exactly the message-bar item holding
  `pb` (renamed from `finish_step_progress`; it is not step-specific).

The static methods on `SchematisationWizardBase` are removed and callers and
tests are updated.

`start_model_tracker_process` no longer pushes
"Revision uploaded; model creation started."; both upload flows end with the
Processes prompt, which already reports where to follow progress.

## Consequences

- Busy bars, step bars and plain bars share one way to update and remove.
- The new-schematisation flow loses one redundant info message.
