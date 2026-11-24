---
type: decision
id: 20261123-1612-remove-generate-raster-results
date: 2026-11-23
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/result_browser.py
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/workers/download.py
  - rana_qgis_plugin/utils/api.py
tags: [results-browser, lizard, raster]
participants: [engineer, implementation-agent]
---

# Remove "Generate raster results" from the results browser (full removal)

## Context
ResultBrowser offers, besides raw/post-processing downloads, a "Generate raster
results" group (raster table + NO DATA / pixel size / CRS settings) that triggers
on-demand raster generation in Lizard via `LizardResultDownloader`.

## Decision
Remove the group and everything that exists only to serve it: dialog widgets,
nodata/pixelsize/crs plumbing in `loader.download_results` and
`_build_result_downloaders`, `LizardResultDownloader`, and API helpers/ScenarioInfo
properties that become unused. No dead code is left behind.

## Consequences
- Users can no longer generate rasters on demand from the dialog.
- `get_selected_results()` returns only result ids.
