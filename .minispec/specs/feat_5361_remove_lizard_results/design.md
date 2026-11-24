---
feature: feat_5361_remove_lizard_results
status: planned
created: 2026-11-23
decisions: [20261123-1612-remove-generate-raster-results]
---

# Remove "Generate raster results" from Results Browser

## Overview
Remove the "Generate raster results" group (and its settings) from `ResultBrowser`, plus all code only used by it.

## Components
- `widgets/result_browser.py`: drop `postprocessed_rasters_group/table`, `inputs_group`, nodata/pixelsize/crs boxes, `check_raster_selected`, raster loop, related selected_* attrs, `scenario_crs`/`pixel_size` ctor args, unused imports. `get_selected_results` returns ids only. Check whether the "still processing" warning stays valid (keep; just remove raster-settings disabling).
- `loader.py` (`download_results`, `_build_result_downloaders`): remove nodata/pixelsize/crs params and the `LizardResultDownloader` branch.
- `workers/download.py`: remove `LizardResultDownloader`.
- `utils/api.py`, `utils/scenario.py`: remove helpers (`request_raster_generate` etc., `pixel_size`, `grid`/`crs`) only if unused after the change (grep first).
- Tests: update/remove tests referencing removed code.

## Out of scope
"Download post-processing results" table and raw download remain unchanged.

## Manual testing
Download results on a scenario with Lizard results + 3Di simulation: dialog shows only raw checkbox + post-processing table; download works. Also scenario with no post-processing results (warning shown).

## Open Questions
- Whether `get_selected_results` return shape change affects tests.
