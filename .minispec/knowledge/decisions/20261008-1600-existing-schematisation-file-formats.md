---
type: decision
id: 20261008-1600-existing-schematisation-file-formats
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/
  - rana_qgis_plugin/loader.py
tags: [schematisation, upload, geopackage]
participants: [engineer, implementation-agent]
---

# Retain SQLite and GeoPackage inputs for existing schematisations

## Context

The legacy Upload existing route accepts both `.gpkg` and `.sqlite` files,
validates the schema, and normalizes SQLite input to a GeoPackage for the
local schematisation structure. Limiting the new route to GeoPackage would
drop existing user capability.

## Options Considered

### Option 1: Retain both formats

Accept `.gpkg` and `.sqlite`, validate the schema, and normalize SQLite to a
GeoPackage when preparing the local schematisation.

- ✅ Preserves legacy-supported inputs.
- ✅ Retains the familiar user workflow.
- ❌ Requires maintaining and testing the normalization path.

### Option 2: GeoPackage only

Accept only `.gpkg` files and require users to convert SQLite files
themselves.

- ✅ Smaller set of input cases.
- ❌ Removes existing functionality and adds user work.

## Decision

Retain support for both `.gpkg` and `.sqlite` inputs, including schema
validation and the legacy normalization behavior where required.

## Consequences

### Positive

- ✅ Existing users can continue uploading either supported file format.

### Negative

- ⚠️ Both formats require validation coverage, and SQLite normalization must
  produce the expected GeoPackage output.

## Code References

- Legacy format selection and normalization:
  `rana_qgis_plugin/legacy/widgets/schematisation_new_wizard.py`
- Legacy schema validation:
  `rana_qgis_plugin/legacy/simulation/utils_ui.py`

## Related Decisions

- `20260511-1413-split-schematisation-wizard`
- `20261008-1540-schematisation-missing-raster-validation`

## Notes

Long-running conversion, validation, or upload work must not freeze QGIS; use
the current task and UI lifecycle patterns rather than legacy thread helpers.
