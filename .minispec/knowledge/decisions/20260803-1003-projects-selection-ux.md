# Decision: Projects Selection UX — Checkboxes with Bulk Actions

**Date:** 2026-08-03  
**Status:** Accepted  
**Feature:** feat_425_project_selector

## Decision

Use **checkboxes** per row (checked = visible in browser) with **Check All** and **Uncheck All** toolbar buttons and Shift+click range toggle.

## Options Considered

**A. Checkboxes (chosen)** — `Qt.CheckStateRole` on each row  
**B. Qt extended multi-select** — native Ctrl+click / Shift+click selection mode

## Rationale

- Checkboxes map semantically to "this project is visible" — unambiguous meaning
- Native multi-select (B) conflates "selected in dialog" with "visible in browser", which is confusing
- Check All / Uncheck All are trivially implemented with checkboxes
- Range toggling via Shift+click requires custom logic for checkboxes but is manageable

## No Pagination

The selection dialog loads all projects at once (no pagination). Pagination makes cross-page selection awkward and the filtering is sufficient to narrow down large project lists.
