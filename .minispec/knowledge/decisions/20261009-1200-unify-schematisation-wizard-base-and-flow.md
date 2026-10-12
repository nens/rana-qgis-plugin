---
type: decision
id: 20261009-1200-unify-schematisation-wizard-base-and-flow
date: 2026-10-09
status: accepted
supersedes:
  - 20260511-1413-split-schematisation-wizard
  - 20261008-1630-shared-schematisation-creation-flow
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/schematisation_new_wizard.py
  - rana_qgis_plugin/loader.py
tags: [schematisation, wizard, loader, refactor]
participants: [engineer, implementation-agent]
---

# Use a shared base for schematisation wizards and orchestration

## Context

The Loader's Upload existing and From scratch methods duplicate the same
authentication check, organisation fetch/validation, wizard execution, result
validation, and initial-revision upload handoff. The two wizards also duplicate
common QWizard setup, output initialization, and close behavior. A shared Loader
orchestrator will rely on the same wizard result interface in both routes.

The earlier decisions preferred independent wizard classes and module-level
helpers. They were made before the common caller-side wizard contract and the
current duplicated QWizard setup were evaluated together. The page structures
and preparation flows remain different; only their shared interface and
framework setup are being consolidated.

## Options Considered

### Option 1: Lightweight shared wizard base and Loader helper (chosen)

Introduce `SchematisationWizardBase(QWizard)` for common constructor state,
output attributes, shared controls/lifecycle, and the output contract. Keep page
setup and route-specific validation/build flow in each subclass. Extract one
Loader helper for common authentication, organisation, execution, and upload
orchestration.

- ✅ Makes the common wizard interface explicit while retaining separate flows.
- ✅ Removes repeated Loader checks and shared wizard boilerplate.
- ✅ Keeps the base focused; it does not own page composition or route logic.
- ❌ Adds a small inheritance relationship that must remain narrow.

### Option 2: Independent wizards with module-level helpers

Keep each wizard independent and use opt-in helper functions for common setup.

- ✅ Avoids inheritance.
- ❌ Does not establish the shared output contract at construction time.
- ❌ Still requires both classes to repeat wiring and lifecycle conventions.

### Option 3: Single mode-driven wizard

Combine both routes into one wizard with conditional pages.

- ❌ Adds mode-dependent page and validation branching; route-specific flows
  should remain separate.

## Decision

Supersede `20260511-1413-split-schematisation-wizard` and
`20261008-1630-shared-schematisation-creation-flow` with Option 1. The two
wizard classes remain separate and retain their own page setup and preparation
logic, but both inherit `SchematisationWizardBase` for their common interface
and QWizard lifecycle setup. `Loader` uses a shared private orchestration
helper, supplied with a factory for the route-specific wizard.

Do not promote wizard helpers to module-level functions merely for style
consistency. `prepare_existing_schematisation` and
`copy_existing_schematisation_content` remain associated with the Upload
existing flow. `get_paths_from_geopackage` is used by both flows, so move it to
`SchematisationWizardBase` as a static method; both subclasses can use the
shared class helper without one wizard depending on the other's class. This is
a reuse boundary, not a blanket conversion of static methods.

Give each wizard a distinct QSettings size key. Save the size through the shared
close lifecycle so all close paths persist it consistently.

## Consequences

### Positive

- ✅ Loader's common setup and initial-upload handoff have one implementation.
- ✅ Shared wizard output fields and setup have one owner.
- ✅ Route-specific UI and build logic remain clear and separate.
- ✅ Window-size state is isolated by wizard type.

### Negative

- ⚠️ The base class must remain limited to genuinely common interface and
  lifecycle behavior; it must not absorb page or route-specific logic.
- ⚠️ Existing tests that patch `UploadExistingSchematisationWizard`'s static
  raster-path helper must be updated to patch the base-class helper.

## Code References

- `rana_qgis_plugin/loader.py:327-442`
- `rana_qgis_plugin/widgets/schematisation_new_wizard.py:79-446`

## Related Decisions

- Supersedes `20260511-1413-split-schematisation-wizard`
- Supersedes `20261008-1630-shared-schematisation-creation-flow`
