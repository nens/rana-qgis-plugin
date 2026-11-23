---
feature: feat_5361_remove_lizard_results
status: planned
created: 2026-11-23
chunk_size: medium
total_tasks: 4
estimated_lines: ~450 removed, ~30 changed
---

# feat_5361_remove_lizard_results Tasks

## Overview
Remove the "Generate raster results" group from the results browser and all code that only served it. Chunks are mostly deletions, so line counts are larger than the usual medium target but low-risk to review.

## Task List

### Core removal

#### Task 1: Remove raster generation from ResultBrowser and loader
- **Estimate:** ~140 lines removed/changed
- **Files:** `rana_qgis_plugin/widgets/result_browser.py`, `rana_qgis_plugin/loader.py`
- **Description:** In `ResultBrowser`, remove `postprocessed_rasters_group/table`, `inputs_group`, nodata/pixelsize/crs widgets, `check_raster_selected`, the timeseries-rasters loop, `selected_nodata/pixelsize/crs`, and the `scenario_crs`/`pixel_size` ctor args. `get_selected_results()` returns only `selected_results`. Keep the "still processing" warning but drop disabling of raster settings. In `loader.download_results`, construct the dialog without crs/pixel size and use ids only. In `_build_result_downloaders`, drop `nodata`, `pixelsize`, `crs` and the `LizardResultDownloader` branch (always `RanaResultDownloader`); remove that import. Must be a single change: dialog and loader share the return signature, so splitting leaves a broken intermediate state.
- **Depends on:** None
- **Acceptance:** Dialog shows raw checkbox + post-processing table only; downloads work (manual test, see Notes); unit tests pass.

#### Task 2: Remove LizardResultDownloader
- **Estimate:** ~155 lines removed
- **Files:** `rana_qgis_plugin/workers/download.py`
- **Description:** Delete class `LizardResultDownloader` (lines ~625-780) and imports that become unused (`get_raster_file_link`, `request_raster_generate`, `build_vrt`, `split_scenario_extent`, any others per linter).
- **Depends on:** Task 1
- **Acceptance:** No references to the class remain (`grep`); pre-commit passes.

### Cleanup of orphaned helpers

#### Task 3: Remove unused API and generic helpers [P]
- **Estimate:** ~110 lines removed
- **Files:** `rana_qgis_plugin/utils/api.py`, `rana_qgis_plugin/utils/generic.py`
- **Description:** Remove `create_raster_tasks`, `request_raster_generate`, `get_raster_file_link` from api.py, and `split_scenario_extent`, `build_vrt` from generic.py (all only used by the removed downloader; re-grep before deleting, and keep `map_result_to_file_name`, still used by loader). Remove now-unused imports.
- **Depends on:** Task 2
- **Acceptance:** Grep shows no remaining usages; unit tests pass.

#### Task 4: Remove unused ScenarioInfo properties and tests [P]
- **Estimate:** ~40 lines removed (incl. tests)
- **Files:** `rana_qgis_plugin/utils/scenario.py`, `tests/test_utils_scenario.py`
- **Description:** Remove `grid`, `get_grid`, `crs`, `pixel_size` (only used by the removed flow; `file_view.py` reads `meta["grid"]` directly) and their tests. Unused `deepcopy` import if applicable.
- **Depends on:** Task 1
- **Acceptance:** `pytest tests` and pre-commit pass.

## Notes
- Tests are removed together with the code they cover; no new tests needed.
- Manual UI testing after Task 1 (first testable state); tasks 2-4 only delete unreferenced code, so a smoke test of the same flow suffices: download results for (a) scenario with Lizard results + 3Di simulation, (b) scenario with post-processing still running (warning shown), (c) scenario without 3Di link.
- Tasks 3 and 4 can run in parallel; every task leaves the plugin in a working state.

## Progress
- [x] Task 1: Remove raster generation from ResultBrowser and loader
- [x] Task 2: Remove LizardResultDownloader
- [ ] Task 3: Remove unused API and generic helpers
- [ ] Task 4: Remove unused ScenarioInfo properties and tests
