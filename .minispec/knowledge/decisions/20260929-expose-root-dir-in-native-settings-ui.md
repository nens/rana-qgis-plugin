---
type: decision
id: 20260929-expose-root-dir-in-native-settings-ui
date: 2026-09-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/widgets/settings_dialog.py
tags: [settings, ux, storage]
participants: [engineer, implementation-agent]
---

# Add root directory field to the native RanaSettingsDialog

## Context

Decision `20260729-1539-settings-scope-backend-url-only` intentionally scoped
the native `RanaSettingsDialog` to backend URL only "for this increment,"
noting scope could expand later once the base auth flow was stable. Issue
#481 requires the root directory to be user-modifiable, and there is
currently no native UI path to configure any storage directory (the legacy
dialog with this control is dead code, see
`20260929-remove-unused-dir-setters`).

## Options Considered

### Option 1: Add root dir field to the native RanaSettingsDialog
- ✅ Only reachable place to configure storage in the current architecture
- ✅ Directly fulfills the ticket's "modifiable option for the user" requirement
- ❌ Expands the settings dialog beyond its original URL-only scope

### Option 2: Settings.py support only, no UI this ticket
- ✅ Keeps this ticket backend-only
- ❌ Leaves the ticket's "modifiable option for the user" requirement
  unfulfilled, since there is no other reachable UI to set it

## Decision

We chose **Option 1**. Add a "Storage" group to `RanaSettingsDialog` with a
root-directory `QLineEdit` and a Browse button (reusing the `is_writable()`
check pattern used in the legacy dialog). On accept, call
`set_rana_root_dir()`.

## Consequences

### Positive
- ✅ Users have a working, reachable way to change the storage location
- ✅ Fulfills the ticket's UI requirement without depending on legacy code

### Negative
- ⚠️ Supersedes the "for this increment" URL-only scope note from
  `20260729-1539-settings-scope-backend-url-only`

## Code References

- `rana_qgis_plugin/widgets/settings_dialog.py:RanaSettingsDialog`
- `rana_qgis_plugin/utils/local_paths.py:is_writable()`
- `rana_qgis_plugin/legacy/widgets/settings_dialog.py` (reference for Browse
  button pattern only)

## Related Decisions

- `20260729-1539-settings-scope-backend-url-only` (partially superseded)
- `20260929-single-root-dir-derived-getters`
