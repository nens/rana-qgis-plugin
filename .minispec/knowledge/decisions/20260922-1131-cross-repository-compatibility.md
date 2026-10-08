---
id: 20260922-1131-cross-repository-compatibility
date: 2026-09-22
status: accepted
---

# Keep the Cross-Repository Results API Backward Compatible

## Context

The feature changes both the Rana QGIS plugin and the sibling `threedi-results-analysis` plugin. They are released separately, and the Results Analysis change may be packaged as a zip and installed manually for validation before the repositories are merged or released together. Existing callers pass `project` or no grouping context.

## Decision

Add `group_path` without removing or renaming `project`:

```python
load_result(result_path, grid_path, project=None, group_path=None)
```

Rana calls the new keyword first. If the installed Results Analysis version rejects that keyword, Rana retries with `project`. If that signature is also unsupported, Rana falls back to the existing two-argument call. Results Analysis chooses `group_path` first, then the existing `project` branch, then the existing standalone branch.

The companion Results Analysis work uses the Rana ticket number, with a branch such as `feat_455_result_layer_grouping`. The two pull requests cross-link, but their merge and release timing does not need to be synchronized.

## Reasoning

- A new Rana version remains usable with an older Results Analysis installation.
- A new Results Analysis version remains compatible with old Rana callers.
- The fallback extends the existing compatibility behavior rather than replacing it.
- Manual installation of an RA zip provides a practical way to test the new behavior before release.
- One design in the Rana repository avoids duplicated specifications for a shared API contract while the RA repository remains free of a new minispec process.

## Consequences

- Rana must distinguish an unsupported keyword `TypeError` from unrelated errors and preserve existing warning behavior.
- Both repositories need tests for their side of the compatibility contract.
- PR descriptions should link the companion change and document which mixed-version combinations were tested.
- Results Analysis should update its `CHANGES.rst` as appropriate for its release process; that release note is not duplicated in this repository.
