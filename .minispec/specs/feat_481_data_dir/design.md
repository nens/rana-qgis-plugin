---
feature: feat_481_data_dir
status: planned
created: 2026-09-29
decisions:
  - 20260929-single-root-dir-derived-getters
  - 20260929-no-data-migration
  - 20260929-remove-unused-dir-setters
  - 20260929-fix-raw-working-dir-readers
  - 20260929-subdir-naming
  - 20260929-expose-root-dir-in-native-settings-ui
  - 20260929-cleanup-cache-scope-unchanged
---

# Single Rana Data Directory Design

## Overview

Ticket: https://github.com/nens/rana-qgis-plugin/issues/481

Today the plugin configures two independent directories:
- `rana_cache_dir()` (default `~/Rana`) — generic Rana project files and publications.
- `hcc_working_dir()` (default `~/Documents/Rana`, backed by legacy `threedi/working_dir`
  QgsSettings key) — schematisation/model working directories.

This feature consolidates both into a single user-configurable root directory
(default `~/Rana`, same as today's cache dir) containing two fixed subfolders:
`"Models and Simulations"` and `"Projects"`. The public getter functions
(`hcc_working_dir()`, `rana_cache_dir()`) keep their existing signatures and are
now derived from the root, so existing call sites across the native codebase
require no changes.

## User Stories

- As a user, I want a single configurable storage location for Rana data
  instead of two separate directory settings, so I don't have to manage
  the on-disk layout of two unrelated folders.
- As a user, I want the default location to match what I already have today
  (`~/Rana`), so existing data continues to be found without extra setup.

## Components

### `utils/settings.py`
- New `rana_root_dir() -> str` / `set_rana_root_dir(path: str) -> None`,
  backed by `RANA_SETTINGS_ENTRY/root_dir`, default `str(Path.home() / "Rana")`.
- `hcc_working_dir()` rewritten to return
  `str(Path(rana_root_dir()) / "Models and Simulations")`, creating the
  directory if missing.
- `rana_cache_dir()` rewritten to return
  `str(Path(rana_root_dir()) / RANA_PROJECTS_DIR_NAME)`, creating the directory if
  missing.
- `set_hcc_working_dir()` and `set_rana_cache_dir()` removed — their only
  caller was the disconnected legacy settings dialog (see Decisions).
- `initialize_settings()` updated to seed the root default and ensure both
  subdirectories exist, replacing the old `threedi/working_dir` default block.

### `simulation/utils_ui.py`, `workers/download.py`
- Both currently read the raw `threedi/working_dir` QgsSettings key directly,
  bypassing `hcc_working_dir()`. Updated to call `hcc_working_dir()` instead,
  so there is a single source of truth for the models/simulations path.

### `widgets/settings_dialog.py` (native `RanaSettingsDialog`)
- New "Storage" group with a root-directory `QLineEdit` + Browse button
  (reusing the `is_writable()` check pattern from the legacy dialog).
  On accept, calls `set_rana_root_dir(...)`.
- This extends the native settings dialog beyond backend-URL-only scope,
  per decision `20260929-expose-root-dir-in-native-settings-ui` (superseding
  the "for this increment" note in `20260729-1539-settings-scope-backend-url-only`).

### `utils/local_paths.py`
- No signature or behavior changes; continues to call `rana_cache_dir()`.

### Legacy (`legacy/`)
- Left untouched. `legacy/widgets/settings_dialog.py` imports
  `set_hcc_working_dir`/`set_rana_cache_dir` and will fail to import after
  removal. This file is unreachable dead code (legacy is disconnected from
  `classFactory`, which loads the native `RanaQgisPlugin` only) and is not
  covered by any test, so the breakage is accepted collateral rather than
  fixed or worked around.

## Data Model / Settings Keys

| Setting | Key | Default | Notes |
|---|---|---|---|
| Root dir | `Rana/root_dir` | `~/Rana` | New, source of truth |
| Models/Simulations dir | *(derived)* | `<root>/Models and Simulations` | via `hcc_working_dir()` |
| Projects dir | *(derived)* | `<root>/Projects` | via `rana_cache_dir()` and `RANA_PROJECTS_DIR_NAME` |
| Legacy `threedi/working_dir` | `threedi/working_dir` | *(unused going forward)* | No longer written; only stale reads remain in legacy dead code |

## Manual Testing Paths

- Native settings dialog: change root dir, verify both subfolders are created
  under the new root immediately (or on first use).
- Open a generic Rana file → verify it lands under
  `<root>/Projects/...`.
- Open/download a schematisation → verify it lands under
  `<root>/Models and Simulations/...`.
- File-open dialogs (`simulation/utils_ui.py:get_filepath`) default to the
  new working dir.

## Out of Scope

- Migrating existing user data from the old `~/Rana` / `~/Documents/Rana`
  locations into the new subfolder layout.
- Fixing the legacy settings dialog or any other legacy code.
- Wiring `cleanup_cache_on_close` into the native UI (it remains legacy-only
  and already scopes cleanup to `rana_cache_dir()` only — no change needed).

## Open Questions

None outstanding — all decisions were resolved during design.
