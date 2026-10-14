---
feature: fix_493_schematisation_group_naming
status: implementing
created: 2026-10-13
chunk_size: adaptive
total_tasks: 3
estimated_lines: 70
---

# Consistent Schematisation Group Naming Tasks

## Overview

Implements `.minispec/specs/fix_493_schematisation_group_naming/design.md`.
The editor-side API is already implemented and installed in the Docker
environment used for manual testing. Rana's TypeError fallback preserves
compatibility with older editor versions.

## Task List

### Core Implementation

#### Task 1: Pass an optional group name to the schematisation editor
- **Estimate:** ~40 lines
- **Files:** `rana_qgis_plugin/simulation/utils.py`
- **Description:** Add optional `group_name=None` to
  `load_local_schematisation()` and pass it to
  `schematisation_editor.load_schematisation()`. Support both older API
  shapes: retry without `group_name` while keeping `parents`, then, if needed,
  retry with only the GeoPackage path when `parents` is also unsupported.
  Re-raise unrelated type errors.
- **Depends on:** None
- **Acceptance:** New editors receive `group_name`; older editors load without
  it whether or not they support `parents`; unrelated TypeErrors are not
  swallowed.
- **Evidence:** Focused tests for supported and unsupported `group_name`,
  plus regression coverage for the existing `parents` fallback.
- **Status:** Complete

#### Task 2: Derive and forward the plain file-item name
- **Estimate:** ~25 lines
- **Files:** `rana_qgis_plugin/loader.py`,
  `rana_qgis_plugin/layer_management/layer_manager.py`
- **Description:** At the loader callback, derive the leaf with
  `PurePosixPath(request.file_item["id"]).name` and pass it to
  `open_rana_schematisation()`. Forward it to `load_local_schematisation()`.
  Update the existing workaround comment to explain that the editor now gets
  the canonical leaf name while Rana still pre-creates/adopts the hierarchy
  for its metadata.
- **Depends on:** Task 1
- **Acceptance:** The leaf passed to the editor exactly matches the final
  component of the Rana file-item ID; parent segments and group tagging are
  unchanged.
- **Evidence:** Focused test asserting the forwarded leaf name and unchanged
  parent hierarchy.

### Integration & Verification

#### Task 3: Verify compatibility and naming end to end
- **Estimate:** n/a (verification)
- **Files:** No files expected; add focused tests if verification exposes a
  gap.
- **Description:** With both repositories' changes available, exercise the
  manual testing paths in the design. Also confirm loading still succeeds
  with an editor version that lacks `group_name` support.
- **Depends on:** Tasks 1-2.
- **Acceptance:** The plain item name appears in both the Layers panel and
  editor dropdown with the new editor, while older editor versions retain
  their previous behavior without failing to load.
- **Evidence:** Focused tests pass and manual test notes cover new-editor and
  compatibility paths.
