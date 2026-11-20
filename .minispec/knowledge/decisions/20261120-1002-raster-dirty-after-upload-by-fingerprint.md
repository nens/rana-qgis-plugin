---
id: 20261120-1002-raster-dirty-after-upload-by-fingerprint
date: 2026-11-20
status: accepted
---

# Raster dirty state after upload is decided by fingerprint

## Decision

The raster fingerprint (`fingerprint_file`) is taken when the upload job is
prepared. On per-file completion it is compared with the current fingerprint.
If equal, the start fingerprint becomes the baseline and the layer is clean. If
different, the layer is set dirty explicitly. Changes to the bytes being
uploaded (external writers) are the user's responsibility and are not guarded.

## Rationale

Rasters cannot be locked from QGIS, but the plugin already tracks raster edit
state via this fingerprint. Reusing it avoids marking a changed file as synced.
