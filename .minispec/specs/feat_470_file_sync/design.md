---
feature: feat_470_file_sync
status: implemented
created: 2026-10-14
decisions:
  - 20261014-close-sync-prompt-unified-hook
  - 20261014-dirty-state-layer-tree-indicator
  - 20261014-native-dirty-property-notification
  - 20261021-style-fingerprint-dirty-detection
---

# Unsynced Rana Changes Visibility

## Overview

Make locally-dirty (not-yet-synced-to-Rana) raster and vector layers visible
in the QGIS layer tree, and warn the user about unsynced changes whenever the
project is about to go away — switching projects or quitting QGIS. This picks
up two items explicitly deferred by `feat_454_open_generic_files`: the visual
treatment of the dirty-state indicator (listed there as out of scope), and the
close-time warning (deferred "in favor of the future automatic sync-on-edit
feature," never implemented).

Builds entirely on existing dirty-state tracking
(`layer_management/dirty_tracking.py`, `rana/data_dirty` / `rana/style_dirty`
custom properties, vector-only data tracking / all-types style tracking per
`20260818-1041-dirty-tracking-vector-only.md`) and the existing fire-and-forget
sync methods on `Loader` (`upload_existing_files`, `upload_styles`) and
`LayerTreeMenuProvider` (`save_style`, `save_data`). No new upload machinery is
introduced.

## User Stories

- As a user, I want to see at a glance which layers in my panel have local
  style or data changes not yet synced to Rana, including when their
  containing group is collapsed.
- As a user, when I close my current project or quit QGIS with unsynced
  changes, I want to be warned and given the option to sync everything before
  proceeding, understanding that the close/quit itself cannot be blocked.

### Edge Cases

- No dirty rana-linked layers exist at close time — no dialog shown.
- Raster "data dirty" has no reliable signal (per
  `20260818-1041-dirty-tracking-vector-only.md`) — rasters never show a data
  indicator and are never included in the close-prompt's data-sync set; only
  their style-dirty state is tracked.
- A dirty layer or group is removed from the panel — prompt once for the
  affected dirty file groups before QGIS removes them. A group removal can
  include multiple dirty child layers and must be handled as one batch.
- Removing a layer/group with an indicator also requires explicit indicator
  cleanup (`QgsLayerTreeView.removeIndicator` does not auto-purge).
- Quitting QGIS triggers `QgsProject.aboutToBeCleared` as part of its own
  shutdown sequence — handled naturally since quitting is a superset of
  closing the project; no separate quit-specific hook or dedup logic needed.
- Removing a layer/group and clearing the project can emit overlapping
  pre-removal signals. Project clearing takes precedence to avoid a second
  prompt for the same close action.
- "Sync now" at close time is fire-and-forget: if QGIS exits before a
  background upload task completes, the sync may be incomplete. Accepted
  tradeoff (see decision) rather than blocking the UI.

## Components

### `layer_management/indicator_manager.py` (new)

Manages `QgsLayerTreeViewIndicator` lifecycle for dirty state:

- Listens to the layer's native `customPropertyChanged(key)` signal, filtering
  for `rana/data_dirty` and `rana/style_dirty`. Existing dirty-tracking
  callbacks remain the only listeners to `afterCommitChanges` and
  `styleChanged`; the indicator manager reacts after those callbacks update
  the custom properties. Removing a dirty property after successful sync
  triggers the same notification path and clears the badge.
- Observes layers added to the project while the plugin is running and starts
  indicator tracking for them. Scanning layers that were already present at
  plugin startup is not required for this feature.
- Listens for layer/group removal to remove now-orphaned indicator objects
  (bookkeeping cleanup; the close-sync prompt handles the user warning).
- One generic icon/tooltip ("Has unsynced changes to Rana") regardless of
  whether it's style, data, or both — no distinction surfaced visually.
- Click behavior: tooltip only. Does not trigger a sync.
- Installed/torn down alongside the plugin's existing `initGui`/`unload`
  lifecycle in `rana_qgis_plugin.py`.

### `layer_management/close_sync_prompt.py` (new)

- Connects to `QgsProject.instance().aboutToBeCleared` for project close,
  project switch, and quit, and to project/tree pre-removal signals for
  individual dirty layer/group removal.
- On tree group removal, scans the subtree while it is still available and
  prompts once for all dirty linked file groups affected by the removal,
  including dirty sibling layers in the same file group. Project removal
  notifications are deduplicated against this pre-detach tree notification.
- During project clearing, per-layer removal notifications are suppressed so
  the project-clear prompt appears only once.
- On fire: scans the layer tree's root group for rana-linked file groups with
  style-dirty or data-dirty content (reusing
  `LayerTreeMenuProvider.file_groups` / `collect_all_layers` and
  `is_style_dirty` / `is_data_dirty`), building two filtered group lists
  (style-dirty, data-dirty — same split `LayerTreeMenuProvider` already uses
  for its own menu actions).
- If both lists are empty, does nothing (no dialog).
- Otherwise shows a dialog listing affected file names with two actions:
  "Sync now" and "Continue without syncing." There is no "Cancel" — the
  underlying signal cannot abort the close, so a button implying it could
  would be misleading. The dialog names the kind of change: "style", "data"
  or "data and style" for a single file, falling back to "data and/or style"
  across several files, where the two kinds may originate from different
  files.
- "Sync now" reuses the existing per-file style/data upload entry points, but
  cannot hand them live layers: the upload task runs after the project is
  cleared or the tree nodes are destroyed. Style inputs are therefore captured
  as a QML snapshot while the layers are still alive, and equivalent layers are
  rebuilt on the worker thread (`workers/style_layers.py`). Captured snapshots
  are discarded on every path that does not reach an upload.

### `LayerTreeMenuProvider` (`layer_tree_menu.py`)

- Rename `_collect_all_layers` → `collect_all_layers` (drop the leading
  underscore; per repo convention, visibility is expressed through
  documentation/imports, not name-mangling) so `close_sync_prompt.py` can call
  it directly alongside the already-public `file_groups`. No further
  extraction — both helpers stay on `LayerTreeMenuProvider` as staticmethods.

### Dirty-state consumers: pull vs push

Three places answer "is this dirty?", and they all read the same custom
properties — but they learn about changes in two fundamentally different ways:

| Consumer | How it learns | Can go stale? |
| --- | --- | --- |
| Context menu | Polls the properties on every right-click | No |
| Close/removal prompt | Polls the layer tree when the prompt fires | No |
| Layer-tree badge | Subscribes via `track_layers` → `customPropertyChanged` | **Yes** |

The two pollers are structurally incapable of going stale. The badge is a
cache whose invalidation depends on a subscription that may never have been
registered, and `update_group` is reachable only from `update_layer`, so a
single untracked layer also freezes every ancestor group badge.

When menu and badge disagree, the badge is almost always the wrong one. The
dirty property is the source of truth; consumers derive from it, and the badge
must never become an input to the others.

## Key Entities

- **Dirty flags** (existing, unchanged): `rana/data_dirty` (vector only),
  `rana/style_dirty` (all layer types) — `layer_management/dirty_tracking.py`.
- **Dirty-state notification** (native): `QgsMapLayer.customPropertyChanged`
  reports changes/removals to those flags; there is no duplicate dirty-state
  store or additional Loader signal.
- **Indicator**: `QgsLayerTreeViewIndicator` instance tracked per layer/group
  node by `IndicatorManager`, not persisted (created for layers added while
  the plugin is running as they become dirty).

## Requirements

### Functional Requirements

- **FR-001**: Users MUST see a visual badge on any layer-tree node (layer or
  ancestor group) backing a rana-linked layer with `rana/data_dirty` or
  `rana/style_dirty` set.
- **FR-002**: Badges MUST reflect current dirty state without stale data —
  appearing promptly when a tracked edit/style-change signal fires, and
  disappearing promptly after a successful sync of that layer.
- **FR-003**: On project close (including quitting QGIS), if any rana-linked
  layer has unsynced style or data changes, System MUST warn the user and
  offer to sync all dirty items before the close proceeds.
- **FR-004**: Before a dirty Rana-linked layer or group is removed, System MUST
  warn about affected unsynced changes and offer to sync them.
- **FR-005**: Removing a group containing multiple dirty layers MUST show one
  prompt listing the affected files and dispatch each dirty file group at
  most once.
- **FR-006**: The close/removal warning MUST NOT claim to be able to cancel
  the close or removal — only "sync now" vs. "continue without syncing" are
  offered.
- **FR-007**: "Sync now" MUST reuse existing per-file style/data upload
  entry points unchanged; this feature MUST NOT introduce new upload,
  locking, or remote-change-guard logic.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A user can tell, without expanding every group, that a
  collapsed folder/file group contains at least one unsynced layer.
- **SC-002**: Closing a project or quitting QGIS with unsynced rana-linked
  changes surfaces exactly one warning; removing a dirty layer/group also
  surfaces one warning for the affected removal operation.
- **SC-003**: Choosing "Sync now" from the warning results in the same
  upload behavior (conflict handling, locking, remote-change guard) as
  manually triggering "Save style/data to Rana" from the context menu.

## Out of Scope

- Schematisation close warning — schematisation layers have no dirty
  tracking today (deliberate, per
  `20260831-0002-schematisation-save-action.md`); extending tracking to them
  is a separate future design.
- Blocking/guaranteed-completion sync at close time (e.g. progress dialog +
  wait) — rejected in favor of fire-and-forget, to avoid a long wait after
  routine project-close/layer-removal actions.
- Distinguishing style-dirty vs. data-dirty visually (two icons) — single
  generic badge only.
- Exact dialog widget choice (`QMessageBox` vs. custom `QDialog`) and the
  specific icon asset for the badge — implementation details, left to task
  breakdown (reuse/extend `icons.py`).

## Known Issues

Found while testing the implemented feature. Recorded here rather than fixed
in place: each has a distinct root cause and the indicator ones affect
`dirty_tracking.py` / `indicator_manager.py` behaviour that other features
depend on.

### KI-001: Style-change detection has per-caller holes

**Corrected 2026-10-21. The original diagnosis was wrong — see below.**

`QgsMapLayer::styleChanged` is not emitted by QGIS automatically when a style
changes. It is emitted imperatively, by each editing widget calling
`emitStyleChanged()`. Coverage is therefore per-caller and patchy, and
`attach_dirty_tracking` inherits every hole.

Confirmed holes (QGIS 4.2.3, `release-4_2` @ `2d2f433`):

- `QgsVectorLayer::setLabeling()` emits nothing. A labeling edit via the Layer
  Styling dock marks the QGIS project dirty but never sets
  `rana/style_dirty` — a real FR-002 violation.
- Vector-tile and annotation layers never emit `styleChanged` at all.
- The doxygen at `qgsmaplayer.h:2096` promises the signal fires "whenever a
  change affects the layer's style", explicitly naming label changes. The
  implementation does not honour this. Treat the docstring as aspirational.

Separately, the layer-tree colour wheel calls `emitStyleChanged()` once per
mouse-move sample during a drag (`QgsColorWheel` emits `colorChanged`
continuously and the menu is kept open), so a single interaction produces
dozens of `setCustomProperty` calls and dozens of full ancestor-group badge
recomputations.

#### Superseded diagnosis — do not repeat this reproduction

This issue originally claimed that editing a symbol through the layer-tree
**Styles ▸ colour wheel** mutates the symbol in place and emits no
`styleChanged`, based on a reproduction of `setColor()` + `triggerRepaint()`.

That reproduction was unfaithful to the UI path and the conclusion was false.
`QgsAppLayerTreeViewMenuProvider::setVectorSymbolColor()`
(`qgsapplayertreeviewmenuprovider.cpp:1318-1361`) clones the symbol, calls
`singleRenderer->setSymbol()`, then calls `layer->emitStyleChanged()`
explicitly. The legend-node variant (`:1434-1455`) does the same. Colour-wheel
edits **are** detected today and any fix must preserve that.

The general lesson: because `styleChanged` is emitted manually, its behaviour
cannot be inferred by mimicking a mutation in a test. Only the caller decides.

#### Fix direction — deferred 2026-10-21

**No fix is planned for now.** A style *fingerprint* was designed and then
rejected for the time being; the analysis is preserved in
`../../knowledge/decisions/20261021-style-fingerprint-dirty-detection.md`
with status `rejected-for-now`.

Rationale: manual testing reports that dirty state tracks correctly in normal
use, and the one mechanism that would close the remaining holes costs roughly
345 lines across three tasks and carries the highest implementation risk in
the feature. The holes below are real as *source readings*, but none has been
observed failing in practice:

- The labeling hole is inferred from `setLabeling()` itself. It was never
  established whether the real UI paths (Layer Styling dock, Layer Properties
  Labels tab) call `emitStyleChanged()` anyway — if they do, the hole is
  empty in practice. Note this concerns **map labels** rendered from attribute
  values, which are part of the style QML; it has nothing to do with layer
  names.
- Vector-tile and annotation layers are not currently opened from Rana, so
  their lack of emission is not reachable.
- The colour-wheel storm is a performance and churn issue, not a correctness
  one. KI-003's fix reduces the recomputation cost independently.

Residual risk if the labeling hole is real: a user edits map labels, closes
the project, and the close prompt does not warn — the styling work is lost
silently.

Cheapest way to settle it, should it ever matter: change a label through the
styling dock and inspect `rana/style_dirty`. A single observation closes this
issue in either direction. Revive the fingerprint decision only if that
observation shows the flag staying unset, or if KI-004 is confirmed real.

### KI-002: Menu, prompt and badge apply different predicates

Three call sites answer the same question differently:

- `LayerTreeMenuProvider.on_context_menu` (`layer_tree_menu.py:109-113`)
  checks only `is_style_dirty` / `is_data_dirty`, with no `is_rana_linked`
  filter, and evaluates `collect_all_layers([node])` across the **entire
  group** unfiltered.
- `collect_dirty_file_groups` (`close_sync_prompt.py:36-40`) additionally
  requires `is_rana_linked`.
- `IndicatorManager.track_layers` (`indicator_manager.py:60`) also requires
  `is_rana_linked`.

Two consequences: a dirty but unlinked layer enables the context-menu sync
actions while showing no badge and raising no close prompt; and one stale
layer in a group enables the actions for all its siblings.

These should share one predicate, defined once in a new `dirty_state.py`.
Placing it there rather than in `dirty_tracking.py` avoids an import cycle,
since the predicate needs `is_rana_linked` from `layer_manager`, which already
imports `dirty_tracking`. The raster asymmetry is deliberate and is tracked
separately as KI-007 — it must not be folded into the shared predicate.

### KI-003: Group badges go stale when a layer is untracked

`IndicatorManager` only tracks a layer if it is Rana-linked at the instant
`layersAdded` fires (`indicator_manager.py:60`). The normal open path is
safe — `set_rana_refs` runs before `add_layer_to_group`
(`layer_manager.py:548`, `:553`) — but `local_linking.py:52,55` sets Rana refs
on layers **already in the project**, long after `layersAdded`. Those layers
are never tracked.

Because every indicator refresh — including ancestor group recomputation — is
driven solely by a tracked layer's `customPropertyChanged`, an untracked
layer means group badges are never recomputed and retain whatever state they
last had.

Confirmed by reproduction. The clear path itself is correct:
`removeCustomProperty` does emit `customPropertyChanged`, and ancestor groups
do clear when the layer is tracked.

Fix direction: track every layer on `layersAdded` and evaluate
`is_rana_linked` at refresh time instead of registration time. Also listen for
changes to the Rana-reference custom properties, so linking and unlinking an
existing layer refreshes its badge. Since `layersAdded` precedes layer-tree
node creation, refresh again when a tracked layer's node is attached; this
also handles layers that were already dirty when added. That removes the
link-ordering dependency entirely, so `local_linking` needs no changes.

The project-reopen variant of this problem is split out as KI-008.

### KI-004: Layers reported dirty immediately on open (RESOLVED 2026-10-21)

Reported: opening a file from Rana leaves the sync actions enabled before any
edit.

**Root cause: Rana's custom properties round-trip through the `.qml`.**
QGIS serialises layer custom properties into named styles, and
`rana/style_dirty`, `rana/data_dirty` and the `rana/*` references are custom
properties. So:

1. The user edits a style; `rana/style_dirty` is set on the layer.
2. Sync calls `saveNamedStyle()`, which writes that flag **into the uploaded
   `.qml`**.
3. A later open downloads the `.qml` and `loadNamedStyle()` **restores the
   flag**, before the user has touched anything.

Confirmed by reproduction (2026-10-21), both manually and headlessly: a saved
style contains `rana/style_dirty`, and loading it sets the property on a
previously clean layer. This also matches the reported asymmetry — a file
whose style has never been synced has no `.qml` and opens clean.

Two further consequences surfaced while fixing it:

- `loadNamedStyle` **replaces** the layer's whole custom-property block. The
  Rana references therefore used to be restored *from the QML* rather than
  from the file being opened, so a style uploaded from one file stamped its
  `rana/file_id` onto any layer that loaded it. References are now written
  **after** the style is applied.
- The flag is baked into styles already stored on the server, so it affects
  every user who opens such a file. Stripping on load was required to fix
  existing data; stripping on save only prevents new pollution.

**Earlier diagnosis was wrong and is superseded.** This issue was previously
attributed to spurious `styleChanged` emitters (`setCurrentStyle`, Layer
Styling dock `apply()`), and recorded as something the KI-001 fingerprint
would make harmless. It would not have: `loadNamedStyle` sets the property
directly and never goes through a signal. Confirming KI-004 therefore does
**not** fire trigger 2 of the fingerprint decision, which remains deferred.

Fix: `strip_rana_properties_from_qml` (`utils/qgis.py`) removes every
`rana/`-prefixed custom property from a QML. It is applied on both sides —
after `saveNamedStyle` when building an upload, and before `loadNamedStyle`
when opening — so local bookkeeping never travels with a shared style.

### KI-005: Dismissing the prompt with Escape raises

`UICommunication.custom_ask` dereferences `msg_box.clickedButton()`
unconditionally (`communication.py:99-102`). Dismissing the QMessageBox via
Escape or the title-bar close leaves that `None`, raising `AttributeError`
inside the project-clear or layer-removal signal handler. A close prompt
should treat dismissal as "Continue without syncing".

### KI-006: Sync preflight blocks the UI thread

"Sync now" is fire-and-forget by design (see Out of Scope), but the preflight
is not. Data sync performs per-file remote verification
(`loader.py:1267-1278`) and style sync verifies its target
(`loader.py:1396-1402`) before creating the background task, both from
synchronous project/layer-tree signal handlers. Closing a project with
several dirty targets freezes the UI on a slow or unreachable network.

### KI-007: Raster dirty state is unknown, not special

`layer_tree_menu.py:119-122` treats every raster as data-dirty
(`isinstance(layer, QgsRasterLayer) or is_data_dirty(layer)`), while
`close_sync_prompt.py:44-46` excludes rasters from the data-dirty set, and
`IndicatorManager` never shows a data badge for them.

This is not two different questions about two different kinds of layer. It is
one question — "does this have unsynced data changes?" — that we currently
cannot answer for rasters, because raster data tracking is unimplemented (per
`20260818-1041-dirty-tracking-vector-only.md`). The divergence is a symptom of
that gap, not a domain distinction, and it should disappear when the gap
closes.

Model the gap honestly as a third state rather than flattening it:

- `CLEAN` — verified no local data changes
- `DIRTY` — verified local data changes
- `UNKNOWN` — cannot determine (rasters, today)

The state is shared; the **effects** differ per consumer:

| Consumer | CLEAN | DIRTY | UNKNOWN |
| --- | --- | --- | --- |
| Context menu | disabled | enabled | enabled — assume the worst, let the user sync |
| Badge | none | shown | none — do not nag about an unverifiable guess |
| Close prompt | silent | guard | silent — do not block on a guess |

Agreed policy (2026-10-21): raster data is always syncable; rasters are
ignored when showing the badge and when guarding on close. The table above is
that policy, expressed so it does not have to be restated at each call site.

Keeping the data-state `isinstance(layer, QgsRasterLayer)` check confined to
the shared dirty-state predicate is the point. Other raster checks, such as
choosing the raster upload data type, are unrelated and need not move. If the
badge and prompt each had to re-check the layer type to decide whether to
suppress, raster logic would scatter back into the consumers — exactly what
KI-002 is about.

When raster data tracking is implemented, rasters stop returning `UNKNOWN`
and every consumer behaves correctly with no changes. Style dirtiness is
unaffected: it is tracked for all layer types and stays two-state.

### KI-008: Reopening a project restores dirty state but not dirty tracking

`attach_dirty_tracking` is called from exactly two sites
(`layer_manager.py:488` and `:552`). Nothing re-applies it on project load —
there is no `projectRead` / `readProject` handler and no startup scan over
existing layers.

Custom properties persist in the `.qgs` XML, so a reopened project restores
`rana/data_dirty` and `rana/style_dirty` along with the Rana refs, but the
signal connections that *maintain* those properties are gone. Reopened Rana
layers are visible, linked, and possibly flagged dirty, yet permanently
untracked: later edits never update the flags and a successful sync cannot
re-dirty them.

Split out of KI-003 and deferred — a future design question, since it also
raises whether persisted dirty flags should be revalidated or cleared on
load.
