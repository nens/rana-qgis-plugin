# Tasks: Resilient Field Rendering for FileView

**Design**: `.minispec/specs/20260720-resilient-field-rendering/design.md`  
**Branch**: `fix_4676`

---

## Phase 1: Foundational — FieldValue infrastructure (TDD)

**Purpose**: Introduce the `FieldValue` dataclass, `make_label()`, and `log_field_errors()` into `file_view.py`. Tests first.

- [x] T001 [US1] Write failing tests for `FieldValue.from_dict`, `FieldValue.from_call`, `make_label`, and `log_field_errors` in `tests/test_file_view.py`
- [x] T002 [US1] Implement `FieldValue` dataclass in `rana_qgis_plugin/widgets/file_view.py` (above `InfoRow`) — tests must pass
- [x] T003 [US1] Implement `make_label()` helper in `file_view.py` — tests must pass
- [x] T004 [US1] Implement `log_field_errors()` helper in `file_view.py` — tests must pass
- [x] T005 [US1] Extend `InfoRow.get_value_widget` to handle `FieldValue` as `value` (auto red color + tooltip)

**Checkpoint**: `docker compose run --rm qgis pytest -v tests/test_file_view.py` passes with new tests green.

---

## Phase 2: User Story 1 — General box (P1)

**Goal**: `update_general_box` in `file_view.py` no longer raises on incomplete metadata.

- [x] T006 [US1] Refactor descriptor fetch in `update_general_box` to use `FieldValue.from_call`
- [x] T007 [US1] Refactor dict accesses in the schematisation branch (`last_rev["commit_message"]`, `last_rev["commit_date"]`, etc.) to use `FieldValue.from_dict`
- [x] T008 [US1] Refactor dict accesses in the non-schematisation branch (`descriptor.get(...)`, `selected_file["user"]`) to use `FieldValue.from_dict`
- [x] T009 [US1] Replace raw `QLabel(...)` calls for display-only fields in `update_general_box` with `make_label()`
- [x] T010 [US1] Call `log_field_errors(self.communication, "FileView general", [...])` at end of `update_general_box`

**Checkpoint**: Selecting a file with complete metadata renders normally; selecting one with missing data shows red "N/A" with tooltips and log entries.

---

## Phase 3: User Story 2 — More box (P2)

**Goal**: `update_more_box` uses `FieldValue` for consistent error styling and logging.

- [x] T011 [US2] Refactor dict accesses in `update_more_box` (descriptor meta, schematisation fields) to use `FieldValue.from_dict`
- [x] T012 [US2] Pass `FieldValue` instances as `InfoRow.value` where applicable in `update_more_box`
- [x] T013 [US2] Call `log_field_errors(self.communication, "FileView more", [...])` at end of `update_more_box`

**Checkpoint**: Selecting a schematisation with incomplete `latest_revision` shows red "N/A" rows in the more box and warn entries in the log.

---

## Dependencies & Execution Order

- Phase 1 must complete before Phase 2 or 3
- Phase 2 and 3 can proceed independently after Phase 1
- Tests (T001) must be written and failing before T002–T004 are implemented

## Manual Testing Paths

- Open FileView for a file with complete metadata → all fields render normally, no log entries
- Open FileView for a file whose descriptor API returns None → affected fields show red "N/A" with tooltip, QGIS log shows error
- Open FileView for a schematisation with missing `latest_revision` → revision-dependent fields show red "N/A", QGIS log shows warnings
