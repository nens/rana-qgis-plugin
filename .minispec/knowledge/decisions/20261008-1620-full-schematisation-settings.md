---
type: decision
id: 20261008-1620-full-schematisation-settings
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/
  - rana_qgis_plugin/simulation/
tags: [schematisation, from-scratch, model-settings]
participants: [engineer, implementation-agent]
---

# Retain full model settings for from-scratch schematisations

## Context

The legacy from-scratch flow does more than create a bare schematisation. Its
settings wizard gathers CRS, flow options, timestep/numerical settings, and
optional raster inputs, then uses those settings to populate the new
GeoPackage schema. A minimal replacement would remove established model setup
capabilities.

## Options Considered

### Option 1: Retain the full legacy settings scope

Port the full configuration and validation flow and populate the resulting
GeoPackage from those inputs.

- ✅ Preserves the user value and functional scope of the legacy route.
- ✅ Produces an initialized model rather than only a bare schematisation.
- ❌ Involves a larger UI and schema-initialization port.

### Option 2: Create a minimal empty schema

Create the basic schematisation and defer detailed settings and raster
population.

- ✅ Smaller first implementation.
- ❌ Removes important existing setup functionality.

## Decision

Retain the full legacy from-scratch settings scope: CRS; 1D, 2D, and 0D
options; timestep and numerical settings; raster inputs; relevant validation;
and population of the new GeoPackage schema from the selected settings.

## Consequences

### Positive

- ✅ The from-scratch route remains useful for configuring a model.
- ✅ Existing validation and schema-population behavior can be preserved.

### Negative

- ⚠️ This route is a substantial vertical slice and should be split into
  implementable tasks after the design is finalized.

## Code References

- Legacy settings page:
  `rana_qgis_plugin/legacy/widgets/new_wizard_pages/settings.py`
- Legacy schema creation:
  `rana_qgis_plugin/legacy/widgets/schematisation_new_wizard.py`
- Current raster mapping:
  `rana_qgis_plugin/simulation/threedi_calls.py:SchematisationApiMapper`

## Related Decisions

- `20260511-1413-split-schematisation-wizard`
- `20261008-1530-schematisation-explanation-step`

## Notes

Port useful behavior, but use current-plugin API, UI, and task patterns. The
legacy implementation remains reference material, not an authority on
threading or lifecycle design.
