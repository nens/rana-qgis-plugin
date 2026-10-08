---
type: decision
id: 20260928-1609-history-pagination
date: 2026-09-28
status: superseded
supersedes: null
superseded_by: 20260928-1812-fetch-all-generic-history
impacts:
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/utils/api.py
tags: [file-history, pagination, api]
participants: [engineer, implementation-agent]
---

# Incrementally Load Older History Entries

## Context

The Rana file-history endpoint is cursor-paginated. Schematisation revisions
use offset/count pagination through the existing 3Di client wrapper. Fetching
all pages before opening a modal could make project-level history slow, while
showing one page forever would hide older history.

## Options Considered

### Option 1: Load more and append

Fetch one page initially and append the next page when the user selects
`Load more`.

- ✅ Avoids unnecessary network requests.
- ✅ Works naturally with Rana's forward-only cursor.
- ✅ Presents the two backend pagination models with one user-facing behavior.
- ❌ Requires retaining cursor/offset state.

### Option 2: Fetch all pages eagerly

Fetch every page before displaying the dialog.

- ✅ Simplest table state after loading.
- ❌ Can block the UI for large project histories.
- ❌ Fetches entries the user may never inspect.

### Option 3: Single page only

Display only the first bounded page.

- ✅ Minimal implementation.
- ❌ Users cannot access older history from the plugin.

## Decision

We chose **Option 1: Load more and append**. Generic history stores the Rana
`next` cursor. Revision history stores the loaded offset and total count. Both
dialogs request a bounded page and append successful results to the existing
model.

## Consequences

### Positive

- ✅ Project/root history does not require an unbounded initial request.
- ✅ Older entries remain available without adding previous-page state.
- ✅ The UI is consistent despite different API pagination schemes.

### Negative

- ⚠️ The API only supports forward navigation; there is no previous-page
  control.
- ⚠️ The synchronous `Load more` request can still briefly block the UI.

## Code References

- Cursor file listing pattern: `rana_qgis_plugin/utils/api.py:207`
- Revision count wrapper: `rana_qgis_plugin/simulation/threedi_calls.py:1261`
