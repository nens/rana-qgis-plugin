---
id: 20260429-1103-batch-download-only
date: 2026-04-29
status: accepted
---

# Batch download does not auto-open files

## Decision

After `BatchFileDownloadWorker` finishes, files are on disk but are not opened in QGIS.
The user opens them manually.

## Rationale

Opening many files automatically after a batch download would be disruptive. Batch
download is a preparation step; the user decides what to open and when.
