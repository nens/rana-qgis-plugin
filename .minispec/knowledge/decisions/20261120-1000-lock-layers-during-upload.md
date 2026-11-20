---
id: 20261120-1000-lock-layers-during-upload
date: 2026-11-20
status: accepted
---

# Lock vector layers read-only while their file uploads

## Decision

While a file is being uploaded, every QGIS vector layer backed by that file
(all tables of a GeoPackage) is set read-only. Layers are unlocked per file as
soon as both upload steps (PUT and `finish_file_upload`) are done, or the
upload failed or was cancelled. If any such layer is in edit mode, the upload
is refused. Edits made outside QGIS are not guarded against.

The lock is shown in the layer tree with a lock indicator (tooltip "Uploading to
Rana — read-only until the upload finishes"), via the existing
`IndicatorManager` and a `rana/upload_lock` layer custom property that also
stores the previous read-only state. Only uploads of existing Rana-linked files
lock layers; new-file uploads do not.

## Rationale

`FileUploadTask` streams the live file from disk, so a save mid-upload can send a
mixed file and leave the layer wrongly marked clean. Copying the file first is
not acceptable: vectors and rasters can be hundreds of MB or more. Allowing
edits during upload would require detection and re-sync tracking, which is more
complex than a clear, temporary read-only state.

## Alternatives considered

- Snapshot copy before upload: doubles disk use for large files.
- Detect changes after upload and skip finish / keep dirty: complex, and still
  leaves a window where a mixed file is sent.
- `BEGIN` read transaction to freeze a GeoPackage: SQLite can still
  checkpoint into the main file during a read, and in rollback-journal mode
  it makes QGIS commits fail with "database is locked".
