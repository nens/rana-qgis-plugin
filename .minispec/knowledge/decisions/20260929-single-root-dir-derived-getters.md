---
type: decision
id: 20260929-single-root-dir-derived-getters
date: 2026-09-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/settings.py
  - rana_qgis_plugin/utils/local_paths.py
tags: [settings, storage, file-paths]
participants: [engineer, implementation-agent]
---

# Consolidate cache dir and working dir into one derived root directory

## Context

`rana_cache_dir()` (default `~/Rana`) and `hcc_working_dir()` (default
`~/Documents/Rana`, backed by the legacy `threedi/working_dir` QgsSettings
key) are two independently configured directories used by both native and
legacy code paths. Issue #481 asks for a single directory with two named
subfolders instead.

## Options Considered

### Option 1: New root setting, old getters become derived wrappers
- ✅ No call-site changes required anywhere `hcc_working_dir()` /
  `rana_cache_dir()` are already used (native `loader.py`, `local_paths.py`,
  `workers/download.py`, etc.)
- ✅ Minimal, contained change per the ticket's instruction to work via
  `utils.settings/utils.local_paths` only
- ❌ Two logically distinct concepts (models vs. project files) now share one
  root, losing independent configurability

### Option 2: Replace old settings/functions entirely, update all call sites
- ✅ Cleaner long-term API
- ❌ Touches legacy files, which the ticket explicitly said to avoid
- ❌ Larger surface area for this increment with no added user value

## Decision

We chose **Option 1**. Add `rana_root_dir()` / `set_rana_root_dir()` backed by
`RANA_SETTINGS_ENTRY/root_dir` (default `~/Rana`, matching today's cache-dir
default). `hcc_working_dir()` now returns
`<root>/Models and Simulations`, and `rana_cache_dir()` returns
`<root>/Rana Projects`. Both continue to ensure their directory exists.

## Consequences

### Positive
- ✅ Single point of configuration for all Rana on-disk storage
- ✅ Zero changes needed at existing call sites

### Negative
- ⚠️ Users can no longer point the two subfolders at unrelated disks/paths
  independently (acceptable per ticket intent)

### Neutral
- The legacy `threedi/working_dir` QgsSettings key is no longer written by
  native code going forward.

## Code References

- `rana_qgis_plugin/utils/settings.py:hcc_working_dir()`
- `rana_qgis_plugin/utils/settings.py:rana_cache_dir()`
- `rana_qgis_plugin/utils/local_paths.py`

## Related Decisions

- `20260929-subdir-naming`
- `20260929-remove-unused-dir-setters`
- `20260929-no-data-migration`
