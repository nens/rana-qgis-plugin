---
type: decision
id: 20260929-remove-unused-dir-setters
date: 2026-09-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/settings.py
  - rana_qgis_plugin/legacy/widgets/settings_dialog.py
tags: [settings, storage, legacy, cleanup]
participants: [engineer, implementation-agent]
---

# Remove set_hcc_working_dir and set_rana_cache_dir

## Context

With `hcc_working_dir()` and `rana_cache_dir()` becoming values derived from
a single root directory, their individual setters (`set_hcc_working_dir()`,
`set_rana_cache_dir()`) no longer have a coherent meaning (setting the
"models" subfolder path independently of the "projects" subfolder path
doesn't fit the new single-root model). Their only caller is
`legacy/widgets/settings_dialog.py`.

`legacy/rana_qgis_plugin.py` (which owns `legacy/widgets/settings_dialog.py`)
is not wired into `classFactory` — the active plugin entry point loads the
native `rana_qgis_plugin/rana_qgis_plugin.py:RanaQgisPlugin` only. The legacy
tree is reference-only per the constitution ("Legacy as Reference, Not
Authority") and is confirmed unreachable at runtime. No test imports
`legacy/widgets/settings_dialog.py`.

## Options Considered

### Option 1: Remove the setters entirely
- ✅ Clean API matching the new single-root model
- ✅ No dead/misleading functions left in `utils/settings.py`
- ❌ Breaks an import in the already-unreachable legacy settings dialog

### Option 2: Keep them as deprecated no-op/compat wrappers
- ✅ Avoids breaking the legacy file's import
- ❌ Confusing semantics (what does "set the working dir" mean when it's
  derived from a root?)
- ❌ Keeps unused code alive for a dead code path

## Decision

We chose **Option 1: remove both setters**. The resulting broken import in
`legacy/widgets/settings_dialog.py` is accepted collateral: the file is
unreachable dead code, not covered by tests, and not fixed per the standing
instruction to never modify legacy code to "fix" it.

## Consequences

### Positive
- ✅ `utils/settings.py` API accurately reflects the new single-root model

### Negative
- ⚠️ `legacy/widgets/settings_dialog.py` will fail to import if ever
  exercised again; this is acceptable since it currently is not reachable

## Code References

- `rana_qgis_plugin/utils/settings.py:set_hcc_working_dir()` (removed)
- `rana_qgis_plugin/utils/settings.py:set_rana_cache_dir()` (removed)
- `rana_qgis_plugin/legacy/widgets/settings_dialog.py` (left as-is, broken import accepted)
- `rana_qgis_plugin/__init__.py:classFactory()` — confirms only the native
  `RanaQgisPlugin` is loaded

## Related Decisions

- `20260929-single-root-dir-derived-getters`
