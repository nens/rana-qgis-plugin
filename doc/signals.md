# Signals through the plugin

The plugin uses Qt signals to connect background work, browser items, dialogs,
and shared UI feedback. There is no single signal bus: most signals are
connected near the components that use them. `ApiErrorSignals` and `Loader`
are the main shared connection points.

## Error signals

`ApiErrorSignals` is passed to data items and dialogs that access the API.

```mermaid
flowchart LR
    Items[Browser items and dialogs] -->|emit| Errors[ApiErrorSignals]
    Errors -->|connection_lost| Provider[Rana data provider]
    Errors -->|request_timed_out| Provider
    Errors -->|fetch_error_occurred| Provider
```

- `connection_lost` indicates that the connection could not be used; the plugin
  shows a "No connection to Rana" warning in the message bar.
- `request_timed_out` indicates a `NetworkTimeoutError` (a subclass of
  `NetworkUnavailableError`); the plugin shows an error bar telling the user to
  check the network connection before retrying.
- `fetch_error_occurred(message, show_dialog)` carries the error text and a
  boolean: `True` shows the message in an error dialog, `False` only writes it
  to the log.

The plugin (`connect_signals()`) listens for these signals and turns them into
the appropriate UI response. Components may also connect directly when they need a
local response.

## Avatar loading

Avatar loading is routed through `Loader` so that widgets do not manage the
worker or cache themselves. Consumers (`ProcessesPanel`, `FileInfoDialog`,
`ProjectsSelectionDialog`) connect to `Loader.avatar_updated` and call
`Loader.get_avatar_for_user` or `Loader.get_avatars_for_users`. These check
`AvatarCache` first; only cache misses reach `Loader.fetch_avatars`, which
starts an `AvatarWorker` (a `QRunnable`).

```mermaid
sequenceDiagram
    participant Widget as ProcessesPanel / FileInfoDialog
    participant Loader
    participant Worker as AvatarWorker
    participant Cache as AvatarCache
    Widget->>Loader: get_avatar(s)_for_user
    alt cache hit
        Loader-->>Widget: pixmap
    else cache miss
        Loader->>Worker: fetch_avatars
        Worker-->>Loader: signals.avatar_ready
        Loader->>Cache: update_avatar
        Cache-->>Loader: avatar_changed
        Loader-->>Widget: avatar_updated
    end
```

The worker's `avatar_ready` is connected to `Loader.on_avatar_ready`, which
updates the cache; the cache's `avatar_changed` is converted by
`Loader.on_avatar_changed` into the UI-facing `avatar_updated` signal. The cache
is not connected to the worker directly. On `avatar_failed`,
`Loader.on_avatar_fetch_failed` removes the cache entry.

## File uploads

The folder action calls `Loader.upload_files()`. Preparation is synchronous;
the actual upload runs as a QGIS task.

```mermaid
sequenceDiagram
    participant Folder
    participant Loader
    participant Task as FileUploadTask
    Folder->>Loader: QAction.triggered
    Loader->>Task: add to QGIS TaskManager
    Task-->>Loader: file_started
    Task-->>Loader: file_failed
    Task-->>Loader: taskCompleted or taskTerminated
    Loader-->>Folder: progress, status, optional refresh
```

The loader consumes task signals and presents progress or completion through
the communication layer. It does not re-emit the task signals.

## Browser actions

Context-menu actions are regular `QAction` signals. They usually call a
method on the item directly:

```mermaid
flowchart LR
    Action[QAction.triggered] --> Item[Browser item method]
    Item --> UI[Dialog, browser refresh, or API operation]
```

Examples include login, logout, refresh, project selection, file information,
and folder upload. Only actions that need shared background orchestration are
routed through `Loader`.

## Layer reference updates

`Loader` emits these signals after a Browser operation succeeds:

- `item_renamed(old_path, new_path, project_id, is_folder)` updates the stored path on
  linked QGIS layers below the renamed file or folder;
- `item_deleted(path, project_id, is_folder)` clears Rana references on affected layers,
  leaving the QGIS layers in the project but disabling Rana sync actions.

Remote changes do not emit these signals. They are checked lazily when a save
operation is started.

## Close/removal sync prompt

[`close_sync_prompt.py`](../rana_qgis_plugin/layer_management/close_sync_prompt.py)
warns about unsynced Rana changes before they'd be lost, and offers to
dispatch the existing sync actions instead. The prompt is the modal
`SyncDialog` (a tree of changed files with checkboxes), shown through
`SyncPromptAction.prompt_and_dispatch` with the buttons "Sync changes now" and
"Continue without syncing". Only checked files are dispatched; style snapshots
that are unchecked or declined are released via `discard_layer_sources`. Two classes handle two genuinely
different scenarios — **`ProjectCloseSyncPrompt`** (closing/switching/
quitting the whole project) and **`LayerRemovalSyncPrompt`** (removing an
individual dirty layer or group while the project stays open) — built on a
shared `SyncPromptAction` (show dialog + dispatch-or-discard) so both show the
identical dialog/outcome. Together they make 7 signal connections (2 in `ProjectCloseSyncPrompt.connect()`, 5 in `LayerRemovalSyncPrompt.connect()`). (Dirty
qualification itself — which groups even count as "unsynced" — is in
[`dirty_tracking.md`](dirty_tracking.md); this section is only about the
connections.)

### `ProjectCloseSyncPrompt` — project clear

```mermaid
sequenceDiagram
    participant QGIS
    participant Prompt as ProjectCloseSyncPrompt
    participant User

    QGIS->>Prompt: aboutToBeCleared
    Prompt->>Prompt: is_clearing = True
    Prompt->>Prompt: scan whole tree, collect dirty groups
    Prompt->>User: SyncDialog via prompt_and_dispatch (Sync changes now / Continue without syncing)
    alt Sync changes now
        Prompt->>Prompt: dispatch checked style / data items
    else Continue without syncing
        Prompt->>Prompt: discard_layer_sources (style snapshots)
    end
    Note over QGIS,Prompt: QGIS then removes every layer as part of\nclearing — layersWillBeRemoved / willRemoveChildren /\nlayersRemoved / removedChildren all fire, but\nLayerRemovalSyncPrompt skips/no-ops while is_clearing is set
    QGIS->>Prompt: cleared
    Prompt->>Prompt: is_clearing = False
```

- `aboutToBeCleared` scans the whole layer tree synchronously and, if any
  group qualifies, shows **one** prompt immediately — the tree is still
  fully intact at this point, so no snapshotting/batching is needed the way
  it is for individual removal (below). `ProjectCloseSyncPrompt` has no
  dedup/batching state of its own.
- Closing/switching the project, and quitting QGIS, all route through this
  same signal (quitting clears the project as part of its own shutdown) —
  see [`20261014-close-sync-prompt-unified-hook.md`](../.minispec/knowledge/decisions/20261014-close-sync-prompt-unified-hook.md) for why there's one hook
  instead of a separate quit-specific one.
- `aboutToBeCleared` is not cancelable, so the dialog only offers "Sync changes
  now" / "Continue without syncing," never "Cancel".
- **This is where the two classes connect**: clearing a project makes QGIS
  internally remove every layer, which fires the exact same signals
  `LayerRemovalSyncPrompt` listens to (below). `is_clearing` (set here,
  cleared on `cleared`) is a public attribute that `LayerRemovalSyncPrompt`
  is given a reference to and reads as a guard, so that cascade of removals
  never produces a second prompt for layers already covered by the one
  whole-project prompt above. It's the one piece of real coupling between
  the two classes — everything else they need (the actual ask/dispatch
  behavior) comes from the shared, stateless `SyncPromptAction` instead.
- `cleared` (fired once QGIS finishes) resets `is_clearing`.
  `LayerRemovalSyncPrompt` connects its own `cleared` handler separately to
  reset its own dedup set (`_prompted_layer_ids`, described next) — the two
  classes don't share that state, only the `is_clearing` flag.

### `LayerRemovalSyncPrompt` — individual layer/group removal

Two independent entry points can fire for the same removal, and they take
different paths:

- `QgsProject.layersWillBeRemoved` (registry-level) is handled directly and
  **immediately** via `prompt_for_layer_ids` — no batching.
- Layer-tree `willRemoveChildren` (tree-level) is routed through the
  **batched** path below, because tree-driven removal of a group fires it
  multiple times for one logical removal.

Both are skipped while `project_close.is_clearing` is `True` (see above).

```mermaid
sequenceDiagram
    participant QGIS
    participant Prompt as LayerRemovalSyncPrompt
    participant Timer as Flush timer (0 ms, single-shot)
    participant User

    alt Registry removal (layersWillBeRemoved)
        QGIS->>Prompt: layersWillBeRemoved
        Prompt->>Prompt: find_dirty_groups(), mark _prompted_layer_ids
        Prompt->>User: SyncDialog via prompt_and_dispatch, immediately
    else Tree-driven removal (willRemoveChildren), possibly several times
        loop each notification, node still live
            QGIS->>Prompt: willRemoveChildren
            Prompt->>Prompt: find_dirty_groups() -> capture_style_items/\ncapture_data_items + SyncChanges.merge, accumulate as plain data
            Prompt->>Prompt: mark layer IDs in _prompted_layer_ids
            Prompt->>Timer: start() (if not already running)
        end
        Timer-->>Prompt: timeout -> flush
        Prompt->>User: SyncDialog via prompt_and_dispatch, once for the whole cascade
    end
    alt Sync changes now
        Prompt->>Prompt: dispatch checked style / data items
    else Continue without syncing
        Prompt->>Prompt: discard_layer_sources (style snapshots)
    end
    Note over QGIS,Prompt: Afterwards, QGIS reports what actually happened
    QGIS->>Prompt: removedChildren
    Prompt->>Prompt: record IDs as tree-only-removed\n(registry removal may or may not follow)
    QGIS->>Prompt: layersRemoved
    Prompt->>Prompt: release those IDs from _prompted_layer_ids
```

- A single group removal tears the tree down bottom-up across **several**
  `willRemoveChildren` notifications (one per sibling file group). Each
  group is only still fully live at the moment of its own notification, so
  `queue_prompt_for_layer_ids` captures that group's upload items as plain
  data (`StyleUploadItem`/`UploadableLayerItem`, snapshotting styles to disk
  since the upload runs after the layers are gone) immediately, accumulating
  them in `_pending_style_items`/`_pending_data_items`. The `SyncChanges`
  shown in the dialog are read from the layers at the same moment and
  accumulated in `_pending_changes` via `SyncChanges.merge`. Only the actual
  prompt is deferred, via a zero-delay `QTimer`, so the whole cascade
  resolves to a **single** prompt once it has finished emitting.
- `_prompted_layer_ids` deduplicates across both entry points and across a
  multi-notification cascade, so the same layer is never queued twice for
  one removal.
- `removedChildren`/`layersRemoved` run afterwards purely for bookkeeping:
  they determine whether a tree detach was tree-only (e.g. the layer stays
  registered but is moved/hidden) or a full registry removal, and release
  the corresponding IDs from `_prompted_layer_ids` only once that's known —
  otherwise a layer that's momentarily detached but not actually removed
  would be silently skipped if dirtied and removed again later.
- `_flush_pending_prompt` passes the pending style items, data items and
  changes to `prompt_and_dispatch`.
- `disconnect()` stops the flush timer and discards any still-pending style
  snapshots, so nothing fires after the plugin unloads.

### On-demand sync

The layer-tree menu actions use the same dialog, without the close/removal
triggers. `LayerTreeMenuProvider.sync` shows it for one kind of change (no kind
sections) before dispatching:

```mermaid
sequenceDiagram
    participant User
    participant Menu as LayerTreeMenuProvider.sync
    participant Changes as SyncChanges
    participant Dialog as SyncDialog
    participant Loader

    User->>Menu: Sync style / data to Rana
    Menu->>Menu: capture_style_items / capture_data_items
    Menu->>Changes: from_layers(include_unknown_data=True)
    Menu->>Dialog: show_kinds=False, "Continue sync" / "Cancel sync"
    alt Continue sync
        Dialog-->>Menu: selected(kind)
        Menu->>Loader: dispatch checked items
    else Cancel sync
        Dialog-->>Menu: rejected, nothing dispatched
    end
```

If there are no items to capture, nothing is shown. Project names come from the
layers; the dialog falls back to the project ID and never calls the API.

## Project-selection dialog

The project-selection dialog combines model, filter, and loader signals:

- `Loader.avatar_updated` updates avatar cells.
- `FilterBar.filters_changed` updates the project list.
- Model `dataChanged` and `modelReset` synchronize checkbox state.
- View and button `clicked`, `accepted`, and `rejected` signals drive user
  interaction.

## Adding a new signal flow

Document new flows as a separate section containing:

1. The triggering signal and component.
2. The receiver or worker it invokes.
3. Signals emitted during processing.
4. The final UI update, refresh, or error path.

Keep this document focused on connections and ownership; implementation
details belong in the source code or action-specific documentation.
