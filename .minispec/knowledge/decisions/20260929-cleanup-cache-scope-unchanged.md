---
type: decision
id: 20260929-cleanup-cache-scope-unchanged
date: 2026-09-29
status: accepted
supersedes: null
superseded_by: null
impacts: []
tags: [settings, storage, legacy, no-op]
participants: [engineer, implementation-agent]
---

# Cleanup-on-close remains scoped to Rana Projects only, unchanged

## Context

`cleanup_cache_on_close` controls whether Rana cache contents are wiped on
QGIS close. With two directories becoming subfolders of one root, it was
worth checking whether cleanup should now cover both `"Models and
Simulations"` and `"Rana Projects"`, or only the latter (schematisation
working directories likely contain data users want to keep).

Investigation showed:
- `cleanup_cache_on_close()` / `set_cleanup_cache_on_close()` and their only
  call site (`legacy/rana_qgis_plugin.py:269`,
  `cleanup_folder(Path(rana_cache_dir()), ...)`) are entirely within the
  legacy tree, which is disconnected from `classFactory` (dead code, per
  `20260929-remove-unused-dir-setters`).
- The native `RanaSettingsDialog` and native plugin entry point do not expose
  or call this setting at all.
- The existing call site already scopes cleanup to `rana_cache_dir()` only,
  never `hcc_working_dir()`.

## Decision

No code change. Cleanup-on-close already only targets the "Rana Projects"
subfolder (via `rana_cache_dir()`), which is the desired scope. Since the
whole feature is legacy-only and unreachable in the native plugin, there is
nothing to wire up or fix as part of this ticket.

## Consequences

### Positive
- ✅ No risk of accidentally deleting schematisation/model working files on
  close, now or in the future if this legacy code path were ever revived

### Neutral
- This setting remains inactive in the native plugin; exposing it natively
  is out of scope for this ticket and would be a separate feature.

## Code References

- `rana_qgis_plugin/legacy/rana_qgis_plugin.py:269`
- `rana_qgis_plugin/utils/settings.py:cleanup_cache_on_close()`

## Related Decisions

- `20260929-remove-unused-dir-setters`
