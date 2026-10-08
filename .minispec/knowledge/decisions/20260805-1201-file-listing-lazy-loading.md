# Decision: Lazy loading for file tree (per-folder API calls)

**Date:** 2026-08-05
**Status:** Accepted

## Context

The file tree could be loaded eagerly (one API call fetching the full tree on expand) or lazily (one API call per folder, triggered when the user expands that folder). The legacy `FilesBrowser` already uses lazy loading: `fetch_and_populate()` accepts an optional `path` parameter and fetches one level at a time.

## Decision

Use lazy loading. Each `createChildren()` call fetches only the immediate children of that folder/node.

## Reasoning

- Fits naturally with `QgsDataItem.createChildren()` which is designed for lazy population
- The Rana files API supports per-path listing via the `path` query parameter
- Avoids loading large trees upfront; scales to projects with many files
- Consistent with how the legacy widget already works

## Consequences

- Each folder expand triggers a network round trip
- Deep trees may feel slow if many levels are expanded quickly
- **Future optimization:** pre-load the next level alongside the current one if latency becomes a problem — no architectural change needed, just fetch one level ahead in `createChildren()`
