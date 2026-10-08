---
type: decision
id: 20261008-1630-shared-schematisation-creation-flow
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/simulation/workers.py
tags: [schematisation, wizard, upload]
participants: [engineer, implementation-agent]
---

# Keep separate upload/create flows with shared schematisation setup

## Context

Upload existing and From scratch have distinct input and wizard page flows, but
both register a Rana schematisation, create local schematisation state, and
upload an initial revision. An accepted prior decision
(`20260511-1413-split-schematisation-wizard`) chose two independent wizards
with a module-level shared helper rather than one mode-driven wizard or an
inheritance hierarchy.

## Options Considered

### Option 1: Separate flows with shared helper and upload orchestration

Keep distinct entry flows and share common schematisation setup and initial
revision upload behavior.

- ✅ Preserves the different input/page requirements.
- ✅ Avoids conditional logic spread across a combined wizard.
- ✅ Reuses common creation and upload behavior.

### Option 2: One combined wizard

Use a mode selector and conditional pages for both routes.

- ✅ Could share page boilerplate.
- ❌ Reverses the prior decision after the distinct flow shapes were considered.
- ❌ Adds mode-dependent branching to wizard behavior.

### Option 3: Separate flows with duplicated common logic

Keep entry flows separate and duplicate creation/upload handling.

- ✅ Each route can be implemented independently.
- ❌ Duplicates substantial common behavior and increases drift risk.

## Decision

Keep Upload existing and From scratch as separate flows. Share the common
schematisation base setup and initial-revision upload orchestration, following
the module-level-helper approach from `20260511-1413`. The upload work must use
the current plugin's `QgsTask` lifecycle rather than legacy thread workers.

## Consequences

### Positive

- ✅ Route-specific input and UI remain clear.
- ✅ Shared registration, local setup, and upload behavior have one owner.
- ✅ Long-running upload work can keep QGIS responsive.

### Negative

- ⚠️ Shared helper boundaries must stay small and reflect actual duplication;
  avoid a generalized wizard framework.

## Code References

- Prior split-wizard decision: `20260511-1413-split-schematisation-wizard`
- Current revision upload task:
  `rana_qgis_plugin/simulation/workers.py:SchematisationUploadTask`
- Current save-revision orchestration: `rana_qgis_plugin/loader.py:save_revision`

## Related Decisions

- `20260831-0003-schematisation-upload-task`
- `20261008-1620-full-schematisation-settings`

## Notes

The actual current task interfaces should be checked during implementation to
confirm whether the existing task can directly represent an initial revision
or needs a focused extension. This design does not authorize copying the
legacy QThread worker lifecycle.
