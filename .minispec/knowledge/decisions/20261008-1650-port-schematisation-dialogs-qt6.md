---
type: decision
id: 20261008-1650-port-schematisation-dialogs-qt6
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/
tags: [schematisation, dialogs, qt6, migration]
participants: [engineer, implementation-agent]
---

# Port existing schematisation dialogs to Qt 6

## Context

The legacy plugin already has separate UI flows for creating a schematisation
from scratch and uploading an existing schematisation. The current plugin
targets QGIS 4.x and Qt 6. The feature should port those dialogs rather than
designing replacement dialogs from scratch.

## Options Considered

### Option 1: Port the existing dialogs

Keep the established route-specific dialog/wizard flows and adapt them to the
current plugin's Qt 6, API, and lifecycle conventions.

- ✅ Preserves familiar, already-established user workflows.
- ✅ Keeps the distinct page/input needs of the two routes.
- ❌ Requires auditing and adapting legacy widget code for Qt 6 and native
  plugin integration.

### Option 2: Design new dialogs

Replace the legacy flows with newly designed current-plugin UI.

- ✅ Offers a clean UI redesign opportunity.
- ❌ Adds design and implementation scope without a stated need to change the
  existing dialog workflows.

## Decision

Port the existing From scratch and Upload existing dialogs/wizards to Qt 6 and
the current plugin architecture. Reuse their user-facing flows and useful
validation, but do not carry over legacy browser/loader wiring, authentication
helpers, or threading/lifecycle patterns.

## Consequences

### Positive

- ✅ Retains the familiar route-specific dialog flows.
- ✅ Aligns the UI with the project's QGIS 4.x / Qt 6 target.

### Negative

- ⚠️ The port must review Qt API changes and replace legacy integration points
  with current-plugin equivalents.

## Code References

- Legacy wizard/dialogs:
  `rana_qgis_plugin/legacy/widgets/schematisation_new_wizard.py`
- Legacy input pages:
  `rana_qgis_plugin/legacy/widgets/new_wizard_pages/`

## Related Decisions

- `20260511-1413-split-schematisation-wizard`
- `20260928-1755-legacy-migration-boundary`
- `20261008-1630-shared-schematisation-creation-flow`

## Notes

Use QGIS Qt imports and current task/API patterns. Legacy widgets are the
reference for the user flow and behavior, not for application wiring.
