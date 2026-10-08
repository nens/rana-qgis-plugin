---
feature: feat_455_result_layer_grouping
status: planned
created: 2026-09-22
chunk_size: adaptive
total_tasks: 2
estimated_lines: 85
---

# Forward Rana Result Paths to Results Analysis — Tasks

## Overview

Implement the active Rana scenario-result opening flow for
`feat_455_result_layer_grouping`.

The loader continues to own downloading and task completion. The layer manager
will own opening the downloaded scenario result in Results Analysis through the
new standalone function:

```python
open_scenario_results_in_results_analysis(
    local_dir, project, file_item, communication
)
```

The sibling Results Analysis plugin already provides:

```python
load_result(result_path, grid_path, project=None, group_path=None)
```

**Repository/branch:** `rana-as-a-native-datasource` / `feat_455_open_results`

**External prerequisite:** Results Analysis branch
`feat_455_result_layer_group` must provide the `group_path` API. Do not commit
changes to that repository from this task list.

## Model Assignment

- **Luna none:** Tasks 1 and 2. The work is bounded delegation, path
  forwarding, compatibility handling, and focused tests against an existing
  API.
- **Manual validation:** The final cross-plugin checklist has no model
  assignment.

## Task List

### Task 1: Delegate scenario-result opening to the layer manager

- **Repo/Branch:** rana-as-a-native-datasource / `feat_455_open_results`
- **Model:** Luna none
- **Estimate:** ~45 lines
- **Files:** `rana_qgis_plugin/loader.py`,
  `rana_qgis_plugin/layer_management/layer_manager.py`
- **Description:** Add standalone
  `open_scenario_results_in_results_analysis()` to `layer_manager.py`.
  It accepts `local_dir`, `project`, `file_item`, and `communication`; checks
  the result/grid files; finds Results Analysis; builds:

  ```python
  [project["name"], "files"] + file_item["id"].split("/")
  ```

  and calls `ra_tool.load_result()` with `group_path=` but without `project=`.
  Preserve the compatibility sequence: grouped call → project-only call →
  two-argument call. Report warnings through `communication`, and preserve the
  existing dock-widget initialization.

  Update `submit_scenario_result_download()` so its completion callback calls
  this layer-manager function with `request.file_item` and
  `self.communication`. Remove the now-moved implementation from `loader.py`.
  Leave the unused legacy `_add_layer_from_scenario()` method unchanged.
- **Depends on:** None
- **Acceptance:** Interactive and batch scenario-result flows delegate through
  the layer manager, pass the exact file path, and remain usable with older
  Results Analysis signatures.
- **Evidence:** Task 2 tests pass and `git diff --check` succeeds.

### Task 2: Test layer-manager opening and loader delegation

- **Repo/Branch:** rana-as-a-native-datasource / `feat_455_open_results`
- **Model:** Luna none
- **Estimate:** ~40 lines
- **Files:** `tests/loader/test_scenario.py`, `tests/test_layer_manager.py`
- **Description:** Add focused tests for the standalone layer-manager function:
  - project-root and nested file IDs produce the expected ordered path;
  - `group_path` and `project` are forwarded;
  - rejecting `group_path` retries with `project`;
  - rejecting `project` retries with the two-argument call;
  - existing warnings are preserved;
  - unrelated `TypeError` exceptions are re-raised;
  - missing result/grid files do not call Results Analysis.

  Update loader tests to verify the download completion callback delegates with
  `request.project`, `request.file_item`, and `loader.communication`.
- **Depends on:** Task 1
- **Acceptance:** Layer-manager behavior and loader delegation have passing
  assertions for the happy path and every compatibility path.
- **Evidence:**
  `pytest tests/loader/test_scenario.py tests/test_layer_manager.py` passes.

### Manual validation: Perform cross-plugin validation

- **Repo/Branch:** Both repositories; no source changes unless a defect is found
- **Model:** Not applicable
- **Estimate:** ~1 hour
- **Files:** None; record results in the PR description/checklist
- **Description:** With the updated Results Analysis plugin installed:
  - Open a nested scenario result through the active automatic flow and verify
    its layer tree follows `project/files/.../result.zip`.
  - Open two results using the same grid and verify Results Analysis keeps them
    in separate result groups.
  - Use a Results Analysis version that rejects `group_path` and confirm Rana
    falls back without an unhandled exception and shows the existing warning
    where applicable.
  - Test a project-root result and a nested result to confirm there are no
    empty path segments.
- **Depends on:** Tasks 1-2 and the updated Results Analysis plugin installed
- **Acceptance:** The manual checklist passes, or defects are recorded as
  follow-up tasks before release.
- **Evidence:** QGIS screenshots/log notes and linked PR checklist entries.

## Dependencies and execution order

- Task 1 moves the opening responsibility and establishes the layer-manager
  compatibility behavior.
- Task 2 verifies the moved function and loader delegation.
- Manual validation requires the updated Results Analysis plugin and passing
  unit tests.

## Notes

- The group segment is lowercase `"files"` by design; do not change the
  unrelated `files`/`Files` casing behavior in this feature.
- The existing `_add_layer_from_scenario()` method is not part of this move and
  remains unchanged.
- Results Analysis interpretation of `group_path`, per-result layer ownership,
  serialization, and its own tests are maintained in the sibling repository.
- Existing generic file grouping and `RanaLayerRef` behavior must remain
  unchanged.

## Progress

- [x] Task 1: Delegate scenario-result opening to the layer manager
- [x] Task 2: Test layer-manager opening and loader delegation
- [ ] Manual validation: Perform cross-plugin validation
