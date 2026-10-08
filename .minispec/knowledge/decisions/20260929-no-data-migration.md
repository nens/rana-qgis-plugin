---
type: decision
id: 20260929-no-data-migration
date: 2026-09-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/settings.py
tags: [settings, storage, migration]
participants: [engineer, implementation-agent]
---

# Do not migrate existing user data to the new directory layout

## Context

Existing users may already have data under `~/Rana` (old cache dir) and
`~/Documents/Rana` (old working dir). The new root/subfolder layout does not
match either location exactly.

## Options Considered

### Option 1: No migration — new location applies going forward only
- ✅ Simplest, lowest risk
- ✅ No partial-move failure modes, no open-file-handle concerns
- ❌ Users may end up with data in both old and new locations until they
  clean up manually

### Option 2: Detect and migrate existing folders on first run
- ✅ Transparent for the user
- ❌ Real complexity: partial move failures, files open in QGIS, project
  files referencing old absolute paths, cross-platform move semantics
- ❌ Disproportionate for a settings-consolidation ticket

## Decision

We chose **Option 1: no migration**. New downloads and working directories go
to the new location going forward. Existing files remain where they are;
users can move them manually if desired. This should be called out in
release notes.

## Consequences

### Positive
- ✅ No migration code, no failure-mode handling needed for this increment

### Negative
- ⚠️ Users will not automatically see previously downloaded files in the new
  location layout; they may need to re-download or manually move files

## Code References

- `rana_qgis_plugin/utils/settings.py:initialize_settings()`

## Related Decisions

- `20260929-single-root-dir-derived-getters`
