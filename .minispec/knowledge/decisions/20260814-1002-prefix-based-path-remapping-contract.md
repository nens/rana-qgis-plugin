# Decision: Prefix-based path remapping contract for tree-change signals

**Date:** 2026-08-14
**Status:** Accepted

## Context

When a folder is renamed, all items below it have stale paths. The `item_renamed` signal emits one event for the renamed item itself. Future subscribers (e.g. layer panel) need a rule for how to update their tracked paths.

A special case: a single layer opened from a multi-layer file, where an ancestor folder (not the file itself) is renamed. The layer's tracked path includes the full file path, which starts with the old folder path.

## Decision

Subscribers must use **prefix-based path remapping**:

```python
if tracked_path.startswith(old_path):
    tracked_path = new_path + tracked_path[len(old_path):]
```

This is a documented contract, not enforced by code. The signal emitter does not enumerate or notify about individual descendants.

## Reasoning

- One signal event per rename keeps the API simple and avoids the emitter needing to know about the tree structure below the renamed node
- Prefix matching naturally handles all cases: direct file rename (exact match), ancestor folder rename (prefix match), and layer-inside-renamed-file (prefix match on the file path portion)
- The alternative — emitting one signal per affected descendant — would require the emitter to enumerate all children (expensive API call or tree walk) and creates ordering/timing complexity

## Applies to delete too

On `item_deleted(path, is_folder)`: subscribers should invalidate any tracked items whose paths start with the deleted path.
