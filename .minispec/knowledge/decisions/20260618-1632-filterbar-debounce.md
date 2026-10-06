---
id: 20260618-1632-filterbar-debounce
status: accepted
date: 2026-06-18
---

# FilterBar: DebouncedSearchBox with 400ms Delay

## Context

FilterBar currently uses a plain QLineEdit that emits `textChanged` on every keystroke. With server-side filtering, each emission would trigger an API call. We need debouncing.

## Decision

Replace `QLineEdit` with the existing `DebouncedSearchBox` widget (from `utils_search.py`) in FilterBar for text filters. Use a 400ms delay. Combo filters remain immediate (no debounce needed for selections).

Both filter types emit the same `filters_changed(dict)` signal. The consuming browser doesn't need to distinguish which filter triggered the change.

## Alternatives Considered

- **Add debounce logic directly to FilterBar:** Rejected -- `DebouncedSearchBox` already exists and is proven. No reason not to reuse it.
- **1000ms delay (DebouncedSearchBox default):** Rejected -- feels sluggish for a filter-as-you-type UX. 400ms balances responsiveness with avoiding excessive API calls.
- **Debounce combo changes too:** Rejected -- selections are intentional single actions, no need to delay.

## Consequences

- Text input has a 400ms gap before triggering API calls
- Combo changes trigger immediately
- Reuses existing `DebouncedSearchBox` widget, maintaining consistency with `SchematisationBrowser`
