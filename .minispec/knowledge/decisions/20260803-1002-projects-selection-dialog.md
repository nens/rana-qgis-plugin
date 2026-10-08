# Decision: Projects Selection Dialog — Fork Legacy ProjectsBrowser

**Date:** 2026-08-03  
**Status:** Accepted  
**Feature:** feat_425_project_selector

## Decision

Fork `legacy/widgets/projects_browser.py` and adapt it into a new `ProjectsSelectionDialog`, rather than building a fresh widget or using the legacy class directly.

## Options Considered

**A. Fork and adapt (chosen)** — copy and modify  
**B. Build fresh** — new dialog referencing legacy only for API patterns  
**C. Use legacy class as-is** — embed existing `ProjectsBrowser`

## Rationale

- The sorting, filtering (text + contributor combo), avatar delegate, and client-side sort infrastructure are the bulk of the complexity — rewriting them offers little benefit
- The changes needed are minimal and well-scoped: replace context menu with checkboxes, remove pagination, wrap in QDialog
- Option C is unsuitable because the existing widget has a different purpose (open/browse) and threading patterns known to have lifecycle issues
- Building fresh (B) would require re-implementing sort/filter/avatar from scratch — higher risk, more work

## Changes from Legacy

- Wrapped in `QDialog` instead of `QWidget`
- Pagination removed (all matching projects shown at once)
- "Open project" context menu removed
- Checkbox per row added for visibility toggling
- Select All / Uncheck All toolbar buttons added
- Shift+click range toggle supported
- Dialog accepts current hidden set on open, writes updated set on OK
