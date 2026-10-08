---
type: decision
id: 20260803-0810-project-child-population
date: 2026-08-03
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/data_items/rana_item.py
tags: [browser, projects, threading, qgsdataitem]
participants: [engineer, implementation-agent]
---

# Use QGIS built-in createChildren() for project listing

## Context

Projects need to be listed as children of `RanaRootDataItem` in the QGIS Browser panel.
Fetching could take a moment; QGIS must not block. Options were: QGIS built-in deferred
loading via `createChildren()`, or a custom `QThread` worker with streaming inserts.

## Options Considered

### Option A: QGIS built-in `createChildren()`
- ✅ No custom thread management — QGIS handles background execution
- ✅ Follows QGIS data item conventions
- ✅ Built-in diff/merge on refresh avoids full tree teardown when items are stable
- ❌ Items appear as a batch, not one by one

### Option B: Custom `QThread` worker with `addChildItem()`
- ✅ Truly streaming — items trickle in as fetched
- ❌ Custom lifecycle management (legacy threading known to have issues)
- ❌ `paginated_fetch` collects all pages before returning; streaming would require
  further refactoring

## Decision

We chose **Option A**.

`paginated_fetch` already aggregates all pages, so true per-item streaming would require
significant additional work. For a list expected to be a few hundred items at most,
batch population via `createChildren()` is fast enough and far simpler. QGIS's built-in
diff/merge means the tree does not visibly flicker on refresh when items are unchanged.

`addChildItem()` remains available for targeted single-item insertion (e.g. the future
"add project" action) without needing a custom mechanism.

## Consequences

### Positive
- ✅ No custom threading code to maintain
- ✅ QGIS model signals handled correctly out of the box
- ✅ Future child item types (files, etc.) follow the same pattern

### Negative
- ⚠️ All projects appear at once after fetch completes, not progressively

## Code References

- `rana_qgis_plugin/data_items/rana_item.py` — `RanaRootDataItem`
- `rana_qgis_plugin/utils/api.py` — `get_tenant_projects`, `paginated_fetch`
