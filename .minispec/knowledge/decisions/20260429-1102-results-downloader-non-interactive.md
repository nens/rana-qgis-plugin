---
id: 20260429-1102-results-downloader-non-interactive
date: 2026-04-29
status: accepted
---

# ResultsDownloader is non-interactive; defaults extracted to standalone function

## Decision

`ResultsDownloader` takes `result_ids` as a constructor parameter and contains no
dialog code. A standalone `get_default_result_ids(results)` function returns
`(result_ids, download_raw)` matching `ResultBrowser`'s initial checked state:
- `download_raw = True`
- result IDs where name is `"max water depth (file)"` and `attachment_url` is set
- no raster IDs

`ResultBrowser` and batch-mode callers both use this function.

`LizardResultDownloadWorker` is kept until `ResultsDownloader` is confirmed working.

## Rationale

Keeping dialog logic in `loader.py` and download logic in `ResultsDownloader` respects
separation of concerns. A single source of truth for defaults avoids drift between
single and batch behaviour.
