---
id: 20260429-1104-optional-deduplication
date: 2026-04-29
status: accepted
---

# Deduplication in BatchFileDownloadWorker is opt-in

## Decision

`BatchFileDownloadWorker` gains a `deduplicate: bool = True` constructor parameter.
When `False`, the copy-instead-of-re-download logic is skipped entirely. Callers that
include `SchematisationDownloader` or `ResultsDownloader` pass `deduplicate=False`.

## Rationale

The existing deduplication (keyed on `file_id`) is only meaningful for
`RanaFileDownloader`. Schematisation and result downloaders have different identifiers
and should not participate in deduplication. Making it opt-in preserves existing
behaviour for pure-Rana-file batches while not misapplying it to other types.
