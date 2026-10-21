---
feature: feat_470_file_sync
status: in_progress
created: 2026-10-14
decisions:
  - 20261014-close-sync-prompt-unified-hook
  - 20261014-dirty-state-layer-tree-indicator
  - 20261014-native-dirty-property-notification
  - 20261021-raster-file-fingerprint-dirty-detection
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

Reuses existing dirty-state properties
(`layer_management/layer_dirty_flags.py`, `rana/data_dirty` /
`rana/style_dirty`) and vector-only edit-signal tracking per
`20260818-1041-dirty-tracking-vector-only.md`; adds filesystem fingerprinting
for eligible Rana rasters. Sync continues through the existing fire-and-forget
methods on `Loader` (`upload_existing_files`, `upload_styles`) and
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
- Raster "data dirty" has no QGIS edit signal (per
  `20260818-1041-dirty-tracking-vector-only.md`); filesystem fingerprinting
  for Rana-cached rasters is specified below. Non-file-backed rasters and
  linked rasters without a known baseline remain `UNKNOWN`.
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

- **Dirty flags**: `rana/data_dirty` (vectors via edit tracking; eligible
  rasters via fingerprint evaluation), `rana/style_dirty` (all layer types) —
  `layer_management/layer_dirty_flags.py`.
- **Raster data fingerprint** (new): `rana/data_fingerprint` — a digest of
  the Rana raster's local file set at the moment it is known to match the
  server (successful download or upload). Stored on the layer as a custom
  property and persisted with the QGIS project. It is not part of
  `RanaLayerRef`; `clear_rana_refs` removes it with the other Rana bookkeeping.
- **Dirty-state notification** (native): `QgsMapLayer.customPropertyChanged`
  reports changes/removals to those flags; there is no duplicate dirty-state
  store or additional Loader signal.
- **Indicator**: `QgsLayerTreeViewIndicator` instance tracked per layer/group
  node by `IndicatorManager`, not persisted (created for layers added while
  the plugin is running as they become dirty).

## Raster data dirty detection

QGIS rasters have no edit buffer, `afterCommitChanges`, or `isModified()`.
Raster changes made through QGIS Processing, Georeferencer, or raster-editing
plugins are written to disk without a QGIS signal that can serve as a dirty
notification. Track Rana-linked raster data by comparing its current local
file set to a baseline captured when a download or upload has completed
successfully.

### Fingerprint

`local_paths.py:88-97` places each Rana file in a dedicated directory beneath
the cache, co-locating the main raster and its sidecars. Fingerprint that
directory recursively so changes to `.tfw`, `.aux.xml`, `.ovr`, and similar
files are included. The digest is `sha256` over sorted manifest lines in the
form `relative_path|size|mtime_ns`; no file contents are read, so work scales
with the number of directory entries rather than the raster's byte size.

Exclude `*.qml`, because styles are tracked separately through
`rana/style_dirty`, as well as transient `*.tmp`, `*.lock`, `*.gpkg-wal`, and
`*.gpkg-shm` files. A tool that rewrites byte-identical content still changes
the modification time and may produce a safe false-positive `DIRTY`; content
hash confirmation is deferred unless this becomes noisy.

Only evaluate a linked layer whose provider is `gdal` and whose resolved local
source path is inside `rana_cache_dir()`. Other providers and paths are
`UNKNOWN`, not clean or dirty. A missing baseline or missing local directory
also yields `UNKNOWN`, avoiding false claims about pre-existing cache files.
Vectors continue using `afterCommitChanges`; filesystem tracking is enabled
for rasters only.

### Baseline lifecycle and re-downloads

Store the baseline in the layer custom property `rana/data_fingerprint`, next
to the existing Rana metadata. QGIS persists custom properties with the
project. The existing `strip_rana_properties_from_qml` removes all `rana/`
properties by prefix, so the fingerprint cannot leak through a style sidecar.
Unlinking a layer removes the fingerprint property as well as its Rana refs.

Capture or replace the baseline only after the file has been fully written by
a successful download, or after the corresponding data upload succeeds.
Ordinary project/layer open must not establish a missing baseline: an existing
cached file may already contain unsynced changes. If no baseline is available,
the state remains `UNKNOWN` until a successful download or upload establishes
one. A re-download is a known-in-sync event, so after the downloaded file
replaces the local file, update the baseline on the linked layer(s) for that
Rana file; subsequent evaluation is `CLEAN` unless another write occurs.

### Evaluation and watching

The raster evaluator writes `rana/data_dirty` when the fingerprint differs
from the baseline. Matching fingerprints clear the data-dirty property;
absent baselines or missing/unreadable directories produce `UNKNOWN` and must
not leave a stale raster `rana/data_dirty` flag. The consumer-facing
dirty-state predicate reads cached properties and the baseline's presence; it
does not fingerprint the directory. Evaluation runs at lifecycle, watcher,
and prompt-collection points, not from badge refresh or context-menu
predicates. The context menu allows `UNKNOWN`, the badge appears only for
`DIRTY`, and the close/removal prompt includes only `DIRTY` data.

Evaluate existing project rasters when the manager starts / project is read,
newly added linked rasters, and affected rasters after filesystem notifications.
Re-evaluate synchronously before collecting close/removal candidates so a
stale cached property cannot hide a missed write. Menu and indicator code read
the cached property and do not perform directory walks. This startup scan
revalidates raster state and does not reattach the vector edit signals in
KI-008.

Use one `QFileSystemWatcher` with a shared single-shot debounce timer. Watch
the raster directory and its subdirectories for additions/removals, and every
relevant current file (main raster and sidecars) for content changes;
directory watches alone may not report writes to an existing file. Refresh
file watches after directory changes, including atomic replacements, since a
file watch may be dropped when the watched file is renamed or removed. Debounce
bursts (approximately 1.5 seconds), then recompute only affected layers.
Remove watches and signal connections when layers leave the project or the
manager disconnects.

## Requirements

### Functional Requirements

- **FR-001**: Users MUST see a visual badge on any layer-tree node (layer or
  ancestor group) backing a rana-linked layer with `rana/data_dirty` or
  `rana/style_dirty` set.
- **FR-002**: Badges MUST reflect current dirty state without stale data —
  appearing promptly when a tracked edit/style-change signal or raster file
  watcher fires, and disappearing promptly after a successful sync of that
  layer.
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
- **FR-008**: A Rana-linked, file-backed raster MUST be reported `DIRTY` when
  its cached file set differs from the baseline recorded at its last
  successful download or data upload.
- **FR-009**: A successful re-download MUST replace the raster's baseline so
  the newly downloaded file is reported `CLEAN` unless it changes afterward.
- **FR-010**: A missing baseline or an ineligible raster source MUST remain
  `UNKNOWN`; opening an existing cached file MUST NOT silently establish a
  baseline.
- **FR-011**: Fingerprint calculation MUST NOT read raster contents and MUST
  be independent of file byte size. Context-menu and badge refresh paths MUST
  use cached state rather than initiating a directory scan.
- **FR-012**: Raster dirty state MUST be re-evaluated for existing and newly
  added project layers, after relevant filesystem notifications, and before
  close/removal prompt collection.

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
- **SC-004**: A QGIS operation that writes to a linked Rana raster's cached
  file set results in a badge within a few seconds, without reopening the
  project.
- **SC-005**: A successful re-download clears the raster's data-dirty state;
  a subsequent close prompt does not list it unless another local write
  occurs.
- **SC-006**: A linked raster with no baseline or a non-file-backed provider
  remains `UNKNOWN` and does not produce a data badge or close-time data entry.

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
- Filesystem-based dirty detection for vectors, including externally modified
  GPKG/SHP files — vectors continue to use `afterCommitChanges`; enabling a
  second source of vector dirty state is a separate design decision.
- Content-hash confirmation after a stat-manifest change — deferred unless
  safe false-positive dirty reports from identical rewrites prove disruptive.

## Known Issues

Found while testing the implemented feature. Recorded here rather than fixed
in place: each has a distinct root cause and the indicator ones affect
`layer_dirty_flags.py` / `indicator_manager.py` behaviour that other features
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

These should share one predicate, defined once in a new `layer_sync_state.py`.
Placing it there rather than in `layer_dirty_flags.py` avoids an import cycle,
since the predicate needs `is_rana_linked` from `layer_manager`, which already
imports `layer_dirty_flags`. The raster asymmetry is deliberate and is tracked
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

Model the gap honestly as a third state rather than flattening it. This was
the policy before the raster filesystem evaluator was specified; the remaining
`UNKNOWN` cases are defined above:

- `CLEAN` — verified no local data changes
- `DIRTY` — verified local data changes
- `UNKNOWN` — cannot determine (e.g. an unbaselined raster or non-file source)

The state is shared; the **effects** differ per consumer:

| Consumer | CLEAN | DIRTY | UNKNOWN |
| --- | --- | --- | --- |
| Context menu | disabled | enabled | enabled — assume the worst, let the user sync |
| Badge | none | shown | none — do not nag about an unverifiable guess |
| Close prompt | silent | guard | silent — do not block on a guess |

Agreed policy before raster tracking (2026-10-21): rasters were always
syncable; they were ignored by badge and close-prompt data checks. With the
filesystem evaluator specified above, eligible rasters leave `UNKNOWN` once a
baseline exists and follow the same consumer policy as vectors. Remaining
`UNKNOWN` sources stay syncable but do not badge or guard on close.

Keeping the data-state `isinstance(layer, QgsRasterLayer)` check confined to
the shared dirty-state predicate is the point. Other raster checks, such as
choosing the raster upload data type, are unrelated and need not move. If the
badge and prompt each had to re-check the layer type to decide whether to
suppress, raster logic would scatter back into the consumers — exactly what
KI-002 is about.

Raster data tracking is specified in "Raster data dirty detection" above.
Eligible baselined rasters return `CLEAN`/`DIRTY`; non-file-backed rasters and
rasters without a baseline remain `UNKNOWN`. The context menu remains enabled
for `UNKNOWN`, while badges and the close prompt act only on verified `DIRTY`
state. Style dirtiness is unaffected: it is tracked for all layer types and
stays two-state.

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
