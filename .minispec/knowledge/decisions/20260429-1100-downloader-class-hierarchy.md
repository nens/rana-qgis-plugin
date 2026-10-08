---
id: 20260429-1100-downloader-class-hierarchy
date: 2026-04-29
status: accepted
---

# Downloader class hierarchy for batch download

## Decision

Introduce `SchematisationDownloader` (full 3Di download) and `ResultsDownloader`
(Lizard results, non-interactive) as `BaseDownloader` subclasses. Rename the current
`SchematisationDownloader` to `SchematisationGeopackageDownloader`.

## Rationale

`BatchFileDownloadWorker` already accepts `list[BaseDownloader]`. Making all download
types conform to `BaseDownloader` lets batch and single downloads share the same worker
infrastructure without special-casing file types.

Using these new classes for single downloads too (replacing `add_from_schematisation`
and `LizardResultDownloadWorker` direct paths) centralises all download logic.
