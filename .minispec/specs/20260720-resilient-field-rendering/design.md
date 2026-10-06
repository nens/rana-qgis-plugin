# Feature Specification: Resilient Field Rendering for FileView

**Created**: 2026-07-20  
**Status**: Draft  
**Branch**: `fix_4676`  
**Input**: FileView widget throws exceptions on missing file data; need automated safe field extraction with visual error indication and logging.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Graceful display of incomplete file metadata (Priority: P1)

A user selects a file in the browser whose API descriptor returns `None` or has missing keys. Instead of an exception caught at plugin level, the FileView shows "N/A" in red for unresolvable fields and logs the issue.

**Why this priority**: Core problem — eliminates exceptions bubbling out of FileView for missing data.

**Independent Test**: Select a file whose descriptor endpoint fails → fields show red "N/A", QGIS log panel shows error-level message.

**Acceptance Scenarios**:

1. **Given** a file with a failing descriptor API, **When** user selects it in FileView, **Then** affected fields show red "N/A" with tooltip, and `communication.log_err()` is called.
2. **Given** a file with a missing dict key (e.g. no `commit_message`), **When** user selects it, **Then** that field shows red "N/A" with tooltip, and `communication.log_warn()` is called.
3. **Given** a file with complete metadata, **When** user selects it, **Then** all fields render normally with no red labels and no log messages.

---

### User Story 2 - More box uses FieldValue for consistent error handling (Priority: P2)

The more box (`update_more_box`) adopts `FieldValue` so that any field extracted from `descriptor.meta` or schematisation data automatically gets red styling and logging when missing.

**Why this priority**: Extends the pattern to the more box for consistency.

**Independent Test**: Select a schematisation with incomplete `latest_revision` → more box fields show red "N/A" where data is missing.

**Acceptance Scenarios**:

1. **Given** a schematisation missing node/line counts in meta, **When** more box renders, **Then** those rows show red "N/A" and a warning is logged.

---

### Edge Cases

- Descriptor API returns `{}` (empty dict) — fields extracted from it show as missing
- `selected_file["user"]` is `None` — avatar + username degrade gracefully
- Schematisation with `latest_revision: None` — all revision-dependent fields show red

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: FileView MUST NOT raise unhandled exceptions when file metadata is incomplete (scoped to `file_view.py` only; no changes to other modules' exception handling)
- **FR-002**: System MUST display "N/A" in red for any field that could not be resolved
- **FR-003**: System MUST show a tooltip on errored fields explaining what went wrong
- **FR-004**: System MUST log failed API calls via `communication.log_err()`
- **FR-005**: System MUST log missing dict keys via `communication.log_warn()`
- **FR-006**: System MUST NOT log anything when all fields resolve successfully
- **FR-007**: `InfoRow` MUST accept `FieldValue` as its `value` parameter and auto-apply red color when errored

### Key Entities

- **FieldValue**: Dataclass in `file_view.py` wrapping a resolved value with `error: bool` and `error_msg: str`. Created via `from_dict()` or `from_call()`.
- **log_field_errors()**: Helper function in `file_view.py`; logs via communication at appropriate levels.
- **make_label()**: Helper in `file_view.py` creating styled QLabel from FieldValue.

## Technical Design

### Location: `rana_qgis_plugin/widgets/file_view.py`

Add `FieldValue` dataclass, `make_label()`, and `log_field_errors()` alongside existing `InfoRow`/`EditLabel` (lines ~80-142 area).

### Implementation Order (TDD)

1. Write tests in `tests/test_file_view.py` (or `tests/test_field_value.py`) for `FieldValue`, `make_label`, `log_field_errors`
2. Implement `FieldValue`, `make_label`, `log_field_errors` until tests pass
3. Extend `InfoRow.get_value_widget` to handle `FieldValue`
4. Refactor `update_general_box` to use `FieldValue.from_dict`/`from_call`
5. Refactor `update_more_box` similarly

### API Summary

```python
@dataclass
class FieldValue:
    value: Any = None
    error: bool = False
    error_msg: str = ""

    @staticmethod
    def from_dict(d: dict | None, key: str, default=None) -> "FieldValue": ...

    @staticmethod
    def from_call(fn: Callable, *args, **kwargs) -> "FieldValue": ...


def make_label(field_value: FieldValue, bold=False, expanding=False, word_wrap=False) -> QLabel: ...

def log_field_errors(communication: UICommunication, context: str, fields: list[tuple[str, FieldValue]]): ...
```

### Logging logic in `log_field_errors`

- `"API"` or `"returned None"` in error_msg → `communication.log_err()`
- Otherwise (missing keys) → `communication.log_warn()`

### `InfoRow.get_value_widget` change

Add early return when `self.value` is a `FieldValue` instance — auto-applies red color and tooltip from the error state.

## Success Criteria *(mandatory)*

- **SC-001**: No unhandled exceptions from FileView when rendering files with incomplete metadata
- **SC-002**: All errored fields visible as red "N/A" with explanatory tooltip
- **SC-003**: QGIS log panel contains appropriate warn/error messages for every missing field
- **SC-004**: All existing tests pass; new TDD tests cover FieldValue logic

## Manual Testing Paths

- Open FileView for a file with complete metadata → normal rendering
- Open FileView for a file whose descriptor API returns None → red fields + log entries
- Open FileView for a schematisation with missing `latest_revision` → graceful degradation

---

*End of design.*
