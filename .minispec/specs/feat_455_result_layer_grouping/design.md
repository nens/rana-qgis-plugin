---
feature: feat_455_result_layer_grouping
status: planned
created: 2026-09-22
decisions:
  - 20260922-1130-result-grouping-by-file-path
  - 20260922-1131-cross-repository-compatibility
---

# Forward Rana Result Paths to Results Analysis

## Overview

The sibling `threedi-results-analysis` plugin now accepts an optional
`group_path` argument on its public `load_result()` API:

```python
load_result(result_path, grid_path, project=None, group_path=None)
```

This feature only changes `rana-as-a-native-datasource`. When Rana opens a
scenario result, it will pass the result's location in the Rana datasource tree
to Results Analysis. Results Analysis owns the interpretation of that path and
the resulting layer-tree organization; no Results Analysis implementation is
part of this feature.

For a project named `Project` and a file with API ID
`folder/subfolder/result.zip`, Rana passes:

```python
["Project", "files", "folder", "subfolder", "result.zip"]
```

The lowercase `"files"` segment is intentional and follows the existing Rana
layer-grouping convention. The separate `"files"`/`"Files"` display-label issue
is out of scope.

The Results Analysis branch `feat_455_result_layer_group` is an external
prerequisite. It must provide the API above before the new grouped call can be
used successfully, but this feature does not modify or task that repository.

## User Stories

### Forward the automatic scenario result location (P1)

As a Rana user, I want results opened after a scenario download to retain their
source file location so that Results Analysis can place them under the matching
Rana file group.

Acceptance scenarios:

- Given a scenario file with ID `folder/result.zip`, when its result download
  completes, Rana calls Results Analysis with
  `group_path=[project_name, "files", "folder", "result.zip"]`.
- Given a file at the project root or in nested folders, the generated path
  contains the correct segments and no empty segments.

### Remain compatible with installed Results Analysis versions (P1)

As a Rana user, I want result loading to continue working when the installed
Results Analysis plugin predates `group_path` support.

Acceptance scenarios:

- A Results Analysis version that rejects `group_path` is retried with the
  existing `project` call.
- A still older version that also rejects `project` is retried with the
  existing two-argument call.
- Unsupported-keyword fallbacks preserve the current warning behavior; other
  `TypeError` exceptions are not swallowed.

## Edge Cases

- A result file is directly under the project files root.
- A result file has multiple nested folders.
- The file ID is invalid or contains an empty path segment; Rana must not add
  empty group segments.
- Results Analysis is unavailable; the existing warning is retained.
- The installed Results Analysis version supports `project` but not
  `group_path`.
- The installed Results Analysis version supports neither keyword.
- The completion callback retains the originating `file_item` after the
  background download task completes.

## Requirements

- **FR-001**: Rana MUST derive the group path from the existing datasource
  convention: `[project_name, "files"] + file_item["id"].split("/")`.
- **FR-002**: Rana MUST pass the derived path as the `group_path` keyword to
  Results Analysis together with the existing result path and grid path. When
  `group_path` is supported, Rana MUST NOT also pass `project`.
- **FR-003**: The automatic scenario-result completion callback MUST retain
  access to the originating `file_item` when it invokes the Results Analysis
  loader.
- **FR-004**: The active automatic scenario-result flow MUST first try the new
  `group_path` call, then fall back to `project`, then to the existing
  two-argument call when the installed Results Analysis signature rejects the
  newer keyword.
- **FR-005**: Rana MUST only handle `TypeError` instances that identify an
  unsupported keyword; unrelated `TypeError` exceptions MUST be re-raised.
- **FR-006**: Existing warnings for outdated or unavailable Results Analysis
  versions MUST remain available to users.
- **FR-007**: Existing result downloading, local extraction, layer references,
  generic file grouping, and browser data items MUST remain unchanged.
- **FR-008**: Unit tests MUST cover path construction, forwarding, and every
  compatibility path for the active automatic scenario-result flow.

## Components and Interfaces

### `rana_qgis_plugin/loader.py`

- `submit_scenario_result_download()` carries `request.file_item` into the
  task-completion callback and delegates the completed result to the layer
  manager.
- Download orchestration remains in the loader; layer-opening behavior does not.

### `rana_qgis_plugin/layer_management/layer_manager.py`

- A standalone `open_scenario_results_in_results_analysis()` function owns the
  active scenario-result opening behavior, matching the `open_` naming used by
  other layer-manager opening functions.
- It accepts the local directory, project, file item, and communication object;
  constructs `group_path`; forwards the result to Results Analysis; and reports
  warnings through the supplied communication object.
- The communication dependency is explicit rather than introducing new signals
  or return-value conventions for user-facing warnings.

### Results Analysis integration contract

- The installed new Results Analysis plugin accepts
  `group_path: Optional[list[str]] = None` on `load_result()`.
- Rana does not depend on Results Analysis internals, layer classes, or signal
  signatures.

## Testing

- Existing Rana scenario tests in `tests/loader/test_scenario.py` already cover
  completion callbacks, Results Analysis invocation, and the old project-only
  fallback. Extend those tests for the new file context and grouped call.
- Automated tests will verify root and nested file IDs, `group_path` rejection
  followed by the project call, project rejection followed by the two-argument
  call, warning preservation, and propagation of unrelated `TypeError`
  exceptions.
- Manual QGIS testing is required after installing the updated Results Analysis
  plugin: open a nested scenario result through automatic loading and verify
  the expected file-based group. Open two results using the same grid and verify
  Results Analysis shows separate result groups. Also test Rana with an older
  Results Analysis plugin to verify graceful fallback and warning behavior.

## Success Criteria

- **SC-001**: The active automatic scenario-result flow passes the exact
  datasource path to the new Results Analysis `group_path` parameter.
- **SC-002**: Automatic background loading preserves the original file context
  through task completion.
- **SC-003**: New Rana remains usable with Results Analysis versions supporting
  only `project` or only the two positional path arguments.
- **SC-004**: Unit tests cover all forwarding and compatibility paths without
  changing unrelated result/file behavior.
- **SC-005**: Manual QGIS validation confirms the Results Analysis layer tree
  reflects the Rana file location for the active automatic scenario-result
  flow.

## Scope Boundaries

Included: Rana path construction, delegation from the active automatic
scenario-result flow to the layer manager, backward-compatible calls to Results
Analysis, Rana unit tests, and manual cross-plugin validation.

Not included: changing the unused legacy `_add_layer_from_scenario()` method in
`layer_management/layer_manager.py`, any Results Analysis source changes or
tests, computational-grid layer ownership, Results Analysis serialization,
Results Analysis tool-group placement, Rana browser/data-item UI changes,
result download orchestration, `RanaLayerRef` changes, or the `files`/`Files`
casing issue.

## Open Questions

- None for the Rana implementation. The Results Analysis API and grouped-layer
  behavior are maintained in the sibling repository's own feature design.
