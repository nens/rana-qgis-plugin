---
feature: feat_481_data_dir
status: planned
created: 2026-09-29
chunk_size: adaptive
total_tasks: 4
estimated_lines: 140
---

# Single Rana Data Directory Tasks

## Overview

Implement issue #481 by consolidating Rana storage under one configurable root
with derived `Models and Simulations` and `Projects` directories.

## Task List

### Foundation

#### Task 1: Implement root storage setting and derived getters
- **Estimate:** ~70 lines including tests
- **Files:** `rana_qgis_plugin/utils/settings.py`, `tests/utils/test_settings.py`
- **Description:** Add `rana_root_dir()` and `set_rana_root_dir()`, derive both existing directory getters from the root, create both subdirectories, remove the obsolete individual setters, and test defaults, custom roots, derivation, and creation.
- **Depends on:** None
- **Acceptance:** The root defaults to `~/Rana`; custom roots produce the exact two named subdirectories; both directories are created; obsolete setters are gone.
- **Evidence:** Focused settings tests pass.

### Core Implementation

#### Task 2: Route direct working-directory readers through the getter [P]
- **Estimate:** ~15 lines
- **Files:** `rana_qgis_plugin/simulation/utils_ui.py`, `rana_qgis_plugin/workers/download.py`
- **Description:** Replace direct reads of `threedi/working_dir` with `hcc_working_dir()`.
- **Depends on:** Task 1
- **Acceptance:** File dialogs and scenario-result downloads use the derived Models and Simulations directory.
- **Evidence:** Existing unit tests pass; code search finds no native direct reads of the raw key in these paths.

#### Task 3: Add configurable root directory to native settings UI [P]
- **Estimate:** ~50 lines
- **Files:** `rana_qgis_plugin/widgets/settings_dialog.py`
- **Description:** Add a Storage group with a root-directory field and Browse button, validate selected directories with `is_writable()`, and save through `set_rana_root_dir()`.
- **Depends on:** Task 1
- **Acceptance:** The native settings dialog displays the current root, accepts a writable selected directory, and persists it when accepted.
- **Evidence:** Native settings dialog manual test passes; existing dialog tests (if available) pass.

### Integration and Documentation

#### Task 4: Update history and task tracking
- **Estimate:** ~5 lines
- **Files:** `HISTORY.rst`, `.minispec/specs/feat_481_data_dir/design.md`, this file
- **Description:** Add the issue #481 history entry and update design/task status as implementation progresses.
- **Depends on:** Tasks 1–3
- **Acceptance:** History describes the single root and no-migration behavior; design metadata is `planned` until implementation is complete.
- **Evidence:** Diff review confirms documentation matches the implemented behavior.

## Dependencies and Parallelization

- Task 1 is the foundation.
- Tasks 2 and 3 can proceed in parallel after Task 1.
- Task 4 follows the implementation tasks.

## Notes

- Existing user data is not migrated.
- Legacy settings code is intentionally not modified, even though its obsolete imports become invalid.
- Cleanup-on-close remains scoped to `rana_cache_dir()` and is out of scope for the native UI.
- Manual UI paths: change the root in native settings, open a generic file, open/download a schematisation, and verify the file-dialog starting directory.

## Progress

- [x] Task 1: Implement root storage setting and derived getters
- [x] Task 2: Route direct working-directory readers through the getter
- [x] Task 3: Add configurable root directory to native settings UI
- [x] Task 4: Update history and task tracking
