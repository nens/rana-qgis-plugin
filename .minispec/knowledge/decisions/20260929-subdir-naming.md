---
type: decision
id: 20260929-subdir-naming
date: 2026-09-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/settings.py
tags: [settings, storage, naming]
participants: [engineer, implementation-agent]
---

# Subdirectory names: "Models and Simulations" and "Rana Projects"

## Context

Issue #481 marks the two subdirectory names as TBD, suggesting "Models and
Simulations" and "Rana Projects".

## Options Considered

### Option 1: Use the ticket's literal names
- ✅ Matches the ticket text exactly, self-descriptive to end users
- ❌ Contains spaces, requires filesystem sanitization on some paths (already
  handled by existing `sanitize_path_for_filesystem()`)

### Option 2: Short, filesystem-friendly names (`models`, `projects`)
- ✅ No spaces, simpler paths
- ❌ Less descriptive; diverges from the ticket's suggested names without a
  strong reason

## Decision

We chose **Option 1**: `"Models and Simulations"` for the schematisation/model
working directory, `"Rana Projects"` for generic project files and
publications.

## Consequences

### Positive
- ✅ Matches user-facing ticket language; clear in a file browser

### Neutral
- Paths built under these subdirectories continue to go through
  `sanitize_path_for_filesystem()` where user/file-derived path segments are
  involved.

## Code References

- `rana_qgis_plugin/utils/settings.py:hcc_working_dir()`
- `rana_qgis_plugin/utils/settings.py:rana_cache_dir()`
- `rana_qgis_plugin/utils/local_paths.py:sanitize_path_for_filesystem()`

## Related Decisions

- `20260929-single-root-dir-derived-getters`
