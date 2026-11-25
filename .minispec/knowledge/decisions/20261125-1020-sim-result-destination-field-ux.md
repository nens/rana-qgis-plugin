---
type: decision
id: 20261125-1020-sim-result-destination-field-ux
date: 2026-11-25
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/simulation/simulation_wizard/page_name.ui
  - rana_qgis_plugin/simulation/simulation_wizard.py
  - rana_qgis_plugin/widgets/name_input_dialog.py
tags: [simulation, wizard, results, destination, ux, validation]
participants: [margriet, agent]
---

# Results-folder row on the wizard name page, picker first

## Context

The destination is separate from the simulation name (see
`20261125-1000-sim-result-destination-separate-from-name`), so a button that
adds a folder prefix to the name no longer fits. With only a picker, the user
never types a path, so relative vs. absolute paths and Windows vs. Unix
separators cannot cause confusion. That makes the picker the simpler first
step.

## Options Considered

- **New row on the name page** (chosen), next to the other metadata (name,
  project, tags).
- Editable field on the summary page: rejected, because the summary page is
  read-only today.
- Typed field first, picker later: rejected. The picker avoids all path-format
  questions.
- Live preview of the full project path under a typed field: rejected as
  unnecessary. Only errors are shown.

## Decision

**Phase 1 (picker):** `Results folder: <read-only label> [Browse…] [Clear]`
- The label shows the full project path, e.g. `/models/river/results/`. When no
  folder is chosen, it shows `/models/river/ (next to schematisation)`.
- `Browse…` opens `RanaFolderPicker`. `Clear` resets to the default (`None`).

**Phase 2 (typed input):** the label becomes an editable line edit with the
placeholder "Next to schematisation (optional)".
- Path rules are in `20261125-1010-sim-result-destination-path-semantics`.
- The field is validated live while typing. The error appears in red under the
  field, and `Next` is blocked while the path is invalid
  (`NamePage.isComplete`).
- Per-segment character rules reuse `validate_item_name`
  (`widgets/name_input_dialog.py`), the same rules used when creating folders on
  Rana. No extra Windows character rules: local downloads already sanitize
  `<>:"/\|?*` via `utils/local_paths.sanitize_path`.

Rana creates missing folders itself, so the folder does not have to exist.

## Consequences

- Phase 1 can be shipped on its own and needs no path parsing.
- No network calls while typing. Only the picker talks to Rana.
