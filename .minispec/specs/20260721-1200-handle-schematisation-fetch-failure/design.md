---
feature: handle-schematisation-fetch-failure
status: planned
created: 2026-07-21
decisions: []
---

# Properly Handle Failure to Retrieve Schematisation from Rana

## Overview

`get_threedi_schematisation` in `rana_qgis_plugin/utils/api.py` currently calls `communication.show_error()` and returns `None` on failure. This creates two problems: the `communication` parameter is threaded through unnecessarily, and 6 call sites don't guard against `None`, causing silent crashes when the API fails.

The fix is to remove the `communication` parameter, raise `FetchError` on failure, and have all 11 call sites catch `FetchError` and handle it explicitly (showing an error via their local `communication` object).

## User Scenarios & Testing

### User Story 1 — API failure is surfaced to the user at all call sites (Priority: P1)

When the Rana API fails to return a schematisation (network error, 404, etc.), the user sees a clear error message and the operation stops cleanly — no crash, no silent failure.

**Why this priority**: 6 call sites currently have a latent crash bug. This is a correctness fix.

**Independent Test**: Can be tested by simulating an API failure (e.g., wrong URL in settings, or no network) and triggering any of the 11 UI paths listed below.

**Acceptance Scenarios**:

1. **Given** the API is unreachable, **When** the user selects a schematisation in the Files Browser, **Then** an error message is shown and no crash occurs.
2. **Given** the API returns an error, **When** the user clicks "Create 3Di model", **Then** an error is shown and the action stops gracefully.
3. **Given** a valid API, **When** the user performs any of the 11 actions, **Then** normal behaviour is unchanged.

---

### Edge Cases

- What if the caller forgets to catch `FetchError`? — This is now a programming error, not a silent `None`-dereference. It will raise visibly, which is better than the current silent crash.
- Call sites that previously returned early on `None` must now return early in the `except` block instead.

## Requirements

### Functional Requirements

- **FR-001**: `get_threedi_schematisation` MUST raise `FetchError` (already defined in `api.py`) instead of calling `communication.show_error()` and returning `None`.
- **FR-002**: `get_threedi_schematisation` MUST NOT accept a `communication` parameter.
- **FR-003**: All 11 call sites MUST wrap the call in `try/except FetchError` and show an appropriate error message to the user via their local `communication` object.
- **FR-004**: Call sites that previously checked `if schematisation:` MUST replace that check with the `except FetchError` block.
- **FR-005**: Call sites that previously assumed success (no `None` check) MUST add a `try/except FetchError` block.

### Call Sites

| # | File | ~Line | Current guard | Change |
|---|------|-------|---------------|--------|
| 1 | `widgets/file_view.py` | 251 | `if schematisation:` | Replace with try/except |
| 2 | `loader.py` | 414 | `if schematisation:` | Replace with try/except |
| 3 | `loader.py` | 521 | `if schematisation:` | Replace with try/except |
| 4 | `loader.py` | 775 | ❌ none | Add try/except |
| 5 | `loader.py` | 786 | ❌ none | Add try/except |
| 6 | `loader.py` | 893 | ❌ none | Add try/except |
| 7 | `loader.py` | 940 | ❌ none | Add try/except |
| 8 | `loader.py` | 1669 | ❌ none | Add try/except |
| 9 | `widgets/files_browser.py` | 559 | `if schematisation:` | Replace with try/except |
| 10 | `widgets/utils_file_action.py` | 191 | `if schematisation:` | Replace with try/except |
| 11 | `widgets/revisions_view.py` | 171 | ❌ none | Add try/except |

## Implementation Notes

The error message shown to the user at each call site should mirror the one currently in `get_threedi_schematisation`:
```
self.communication.show_error(f"Failed to retrieve schematisation: {e}")
```
where `e` is the caught `FetchError`.

For call sites that previously returned early on `None` (cases ✅), the except block should return in the same way. For call sites that had no guard (cases ❌), the except block should return or abort the operation in a way consistent with the surrounding method.

## UI Paths for Manual Testing

1. Select a schematisation in the browser → FileView loads (`file_view.py`)
2. Select a schematisation → click Download (`loader.py` ~414)
3. Select multiple files incl. schematisation → "Open projects recursively" (`loader.py` ~521)
4. Select a schematisation → Actions → "Create 3Di model" (`loader.py` ~775)
5. Select a schematisation → Actions → "Export schematisation" (`loader.py` ~786)
6. Select a schematisation → Actions → "Delete 3Di model" (`loader.py` ~893)
7. Select a schematisation → Actions → "Start simulation" (`loader.py` ~940)
8. Select a schematisation → Actions → "Upload revision" (`loader.py` ~1669)
9. Navigate to a schematisation in the files browser (`files_browser.py`)
10. Select a schematisation → click "Open in browser" (`utils_file_action.py`)
11. Select a schematisation → expand "Revisions" panel (`revisions_view.py`)

## Success Criteria

- **SC-001**: No call site can silently crash due to an unguarded `None` return from `get_threedi_schematisation`.
- **SC-002**: `get_threedi_schematisation` has no `communication` parameter.
- **SC-003**: All 11 call sites show a user-facing error message when the API fails.
- **SC-004**: All existing unit tests pass; new unit tests cover the `FetchError` raise path in `get_threedi_schematisation`.

## Open Questions

- None — the issue is fully specified.
