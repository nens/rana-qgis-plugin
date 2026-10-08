# Decision: Loader hosts mutation methods and tree-change signals

**Date:** 2026-08-14
**Status:** Accepted

## Context

Rename and delete are synchronous API calls (no threading needed). Two questions: where should the API call live, and where should the cross-panel signals live?

### Options considered

**Option A — Signals on Loader, API calls on data items**: Data items call `api.move_file()`/`api.delete_tenant_project_file()` directly (consistent with how read operations like `get_tenant_project_file()` are called today), then emit via `self.loader.item_renamed.emit(...)`. Minimal change.

**Option B — Loader hosts both mutation methods and signals**: Loader gains `rename_item()` and `delete_file()` methods that perform the API call AND emit the signal. Data items / GuiProvider call these instead of `api.py` directly.

## Decision

Option B — Loader hosts both mutation methods and signals.

## Reasoning

- Co-locating mutation + signal emission in one place ensures signals are only emitted on actual success, without relying on every caller remembering to emit
- Loader is the one persistent, shared object in the plugin; data items are ephemeral (recreated on every `refresh()`) and cannot safely own long-lived signals
- As the plugin grows, other UI elements (e.g. layer panel) may also need to trigger renames/deletes — centralizing on Loader gives them a single entry point
- The "Loader does background orchestration" role naturally extends to "Loader does all tree mutations" — these are the write-side operations that change Rana state

## Signals

- `item_renamed = pyqtSignal(str, str, bool)` — `(old_path, new_path, is_folder)`
- `item_deleted = pyqtSignal(str, bool)` — `(path, is_folder)`

## Addendum (2026-08-17): Rename and delete become asynchronous

The "no threading needed" premise above held for the initial
`feat_451_simple_context_menu_actions` implementation. `feat_451_with_tasks`
moves rename, delete, and create-directory onto an asynchronous Loader-owned
operation lifecycle (stable operation IDs; `mutation_started` /
`operation_succeeded` / `operation_failed` / `mutation_finished` signals) so
slow backend requests no longer block the UI thread.

Loader remains the sole owner of both the mutation call and signal emission,
per the original decision — only the execution mechanism (synchronous call vs.
background task) changes. The `item_renamed`/`item_deleted` signals above are
superseded by the richer operation lifecycle signals; see
`.minispec/specs/feat_451_with_tasks/design.md` for the current contract.
