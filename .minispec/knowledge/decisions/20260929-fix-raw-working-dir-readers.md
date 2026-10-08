---
type: decision
id: 20260929-fix-raw-working-dir-readers
date: 2026-09-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/simulation/utils_ui.py
  - rana_qgis_plugin/workers/download.py
tags: [settings, storage, native]
participants: [engineer, implementation-agent]
---

# Route direct threedi/working_dir QgsSettings reads through hcc_working_dir()

## Context

Two native (non-legacy) call sites read the raw `threedi/working_dir`
QgsSettings key directly instead of calling `hcc_working_dir()`:
`simulation/utils_ui.py:get_filepath()` and
`workers/download.py:ScenarioResultDownload.local_dir`. Once
`hcc_working_dir()` is derived from the new root directory and no longer
writes/reads that legacy key, these two call sites would silently keep
reading a stale or empty value.

## Options Considered

### Option 1: Mirror the value into the legacy key on every root-dir change
- ✅ No changes needed at the two call sites
- ❌ Reintroduces a second, redundant source of truth
- ❌ Fragile — any future direct reader would have the same silent-staleness risk

### Option 2: Update the two call sites to use hcc_working_dir()
- ✅ Single source of truth, no duplicated state
- ✅ Small, targeted change (two call sites)
- ❌ Touches files outside `utils.settings` / `utils.local_paths`

## Decision

We chose **Option 2**. Both call sites now call `hcc_working_dir()` directly
instead of reading `QSettings()`/`QgsSettings()` for the raw key.

## Consequences

### Positive
- ✅ Single source of truth for the models/simulations working directory
- ✅ No stale-value risk from a mirrored legacy key

### Negative
- ⚠️ Slightly exceeds the ticket's literal instruction to touch only
  `utils.settings`/`utils.local_paths`, but is necessary for correctness

## Code References

- `rana_qgis_plugin/simulation/utils_ui.py:177` (`get_filepath()`)
- `rana_qgis_plugin/workers/download.py:197` (`ScenarioResultDownload.local_dir`)
- `rana_qgis_plugin/utils/settings.py:hcc_working_dir()`

## Related Decisions

- `20260929-single-root-dir-derived-getters`
