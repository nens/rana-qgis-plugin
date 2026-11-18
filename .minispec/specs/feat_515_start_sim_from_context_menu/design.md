---
feature: feat_515_start_sim_from_context_menu
status: designed
created: 2026-11-18
decisions:
  - 20261118-1200-context-menu-action-availability
  - 20261118-1201-loader-simulation-preflight
  - 20261118-1202-shared-model-creation
---

# Start Simulation from Schematisation Context Menu

## Overview

Add an always-available context-menu action for schematisations that starts a
simulation using the latest revision. The action performs prerequisite checks
only after it is clicked, avoiding network requests while the context menu is
being constructed.

## User Stories

- As a user, I want to start a simulation directly from a schematisation so I
  can avoid opening revision history first.
- As a user, I want to create the required model when it does not exist so I
  can continue toward simulation without finding the model-management flow.
- As a user, I want actionable guidance when a model is generating or unusable
  so I know where to monitor or manage it.

## User Flow

1. The action is shown and enabled for every schematisation.
2. On activation, the loader resolves the latest revision and model state.
3. If an enabled, valid model exists, the existing simulation setup flow opens.
4. If a model is being generated, the user is offered the current project's
   Processes view.
5. If no model exists and the model limit allows creation, the user is asked
   whether to create one. Confirmation starts model creation and points to
   Processes.
6. If a model exists but is disabled or invalid, or the model limit prevents
   creation, the user is offered Version history for management.
7. If no revision exists, the user receives a warning and the flow stops.

## Components

### File context-menu action

`FileAction.START_SIMULATION` is included only for
`threedi_schematisation` items. Its callback delegates to the loader and does
not perform API calls during menu construction.

### Loader preflight

The loader owns latest-revision lookup and prerequisite branching. It receives
an optional callback for opening Version history, keeping the loader independent
of the file-item dialog implementation. Existing `start_simulation` remains
responsible for opening the simulation setup dialogs.

### Shared model creation

Model creation and Processes navigation are shared between the new action and
the revision-history dialog. The helper returns an explicit outcome so the
revision-history UI can update its button and row state.

## Data and API

The preflight uses the existing API wrappers to obtain schematisation metadata,
the latest revision, models for that revision, and generating models for the
schematisation. A valid simulation model is enabled and valid. Model capacity
is determined from `threedimodel_limit` and the revisions represented by
existing or generating models.

## Scope Boundaries

This feature does not add revision selection, change the simulation wizard, or
add E2E tests without explicit approval. Preflight requests remain synchronous
unless testing or manual use shows that the click-time delay violates the
responsive-UI principle.

## Manual Testing

- Schematisation with a valid model opens the simulation wizard.
- No model offers model creation and points to Processes after confirmation.
- A generating model offers the Processes view.
- Disabled or invalid models offer Version history.
- A reached model limit offers Version history.
- A schematisation without a revision shows a warning.
