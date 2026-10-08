---
type: decision
id: 20261008-1540-schematisation-missing-raster-validation
date: 2026-10-08
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/
  - rana_qgis_plugin/loader.py
tags: [schematisation, validation, raster]
participants: [engineer, implementation-agent]
---

# Block existing schematisation upload when referenced rasters are missing

## Context

An existing schematisation GeoPackage can reference raster files that are
needed by the model. Uploading only the GeoPackage when one of those files is
missing can leave the resulting remote schematisation incomplete. The legacy
upload-existing flow validates referenced raster paths before completing its
preparation.

## Options Considered

### Option 1: Block and report missing referenced rasters

Do not proceed with upload if a referenced raster cannot be found.

- ✅ Avoids silently creating an incomplete remote schematisation.
- ✅ Preserves the legacy behavior.
- ❌ The user must locate or restore the missing raster before retrying.

### Option 2: Warn and continue

Upload the GeoPackage and any available rasters despite missing references.

- ✅ Allows partial data to be uploaded.
- ❌ Can create an incomplete schematisation that may fail later.

## Decision

Retain the legacy behavior: block the upload-existing flow if a raster
referenced by the GeoPackage is missing. Report the missing file(s) clearly
before starting the upload.

## Consequences

### Positive

- ✅ Prevents a known incomplete-input condition from being uploaded.

### Negative

- ⚠️ Users must repair all missing raster references before uploading.

## Code References

- Legacy raster extraction/validation:
  `rana_qgis_plugin/legacy/widgets/schematisation_new_wizard.py`

## Related Decisions

- `20261008-1520-schematisation-success-followup`

## Notes

Validation and file work must follow the current plugin's responsive UI and
`QgsTask` conventions rather than copying legacy threading/lifecycle code.
